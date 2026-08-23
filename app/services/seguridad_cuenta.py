"""Verificación de correo y TOTP sin almacenar secretos en claro."""

import base64
from datetime import timedelta
import hashlib
import hmac
import secrets
import struct
import time

from flask import current_app, url_for
from flask_mail import Message

from ..extensions import correo
from ..models import Usuario, db, utcnow
from .auditoria import registrar_auditoria


class ErrorSeguridadCuenta(ValueError):
    codigo = "seguridad_cuenta_invalida"


class ErrorEntregaCorreo(ErrorSeguridadCuenta):
    codigo = "correo_verificacion_no_entregado"


def _claves_maestras():
    configuradas = [
        valor.strip()
        for valor in str(current_app.config.get("TWO_FACTOR_ENCRYPTION_KEYS") or "").split(",")
        if valor.strip()
    ]
    if not configuradas:
        configuradas = [str(current_app.secret_key)]
    return [hashlib.sha256(("nexustock:2fa:" + valor).encode()).digest() for valor in configuradas]


def _cifrar(texto):
    nonce = secrets.token_bytes(16)
    clave = _claves_maestras()[0]
    bytes_texto = texto.encode()
    flujo = b""
    contador = 0
    while len(flujo) < len(bytes_texto):
        flujo += hmac.new(clave, nonce + contador.to_bytes(4, "big"), hashlib.sha256).digest()
        contador += 1
    cifrado = bytes(a ^ b for a, b in zip(bytes_texto, flujo, strict=True))
    etiqueta = hmac.new(clave, nonce + cifrado, hashlib.sha256).digest()
    return "v2:0:" + base64.urlsafe_b64encode(nonce + etiqueta + cifrado).decode()


def _descifrar(valor):
    legado = not str(valor).startswith("v2:")
    if legado:
        bruto = base64.urlsafe_b64decode(valor.encode())
        claves = [hashlib.sha256(str(current_app.secret_key).encode()).digest()]
    else:
        partes = str(valor).split(":", 2)
        bruto = base64.urlsafe_b64decode(partes[2].encode())
        claves_disponibles = _claves_maestras()
        indice = int(partes[1])
        claves = [claves_disponibles[indice]] if indice < len(claves_disponibles) else []
    nonce, etiqueta, cifrado = bruto[:16], bruto[16:48], bruto[48:]
    clave = next(
        (
            c
            for c in claves
            if hmac.compare_digest(etiqueta, hmac.new(c, nonce + cifrado, hashlib.sha256).digest())
        ),
        None,
    )
    if clave is None:
        raise ErrorSeguridadCuenta("El secreto de segundo factor no es válido")
    flujo = b""
    contador = 0
    while len(flujo) < len(cifrado):
        flujo += hmac.new(clave, nonce + contador.to_bytes(4, "big"), hashlib.sha256).digest()
        contador += 1
    return bytes(a ^ b for a, b in zip(cifrado, flujo, strict=True)).decode()


def codigo_totp(secreto, instante=None):
    instante = int(instante or time.time()) // 30
    clave = base64.b32decode(secreto, casefold=True)
    digest = hmac.new(clave, struct.pack(">Q", instante), hashlib.sha1).digest()
    desplazamiento = digest[-1] & 0x0F
    numero = (
        struct.unpack(">I", digest[desplazamiento : desplazamiento + 4])[0] & 0x7FFFFFFF
    ) % 1_000_000
    return f"{numero:06d}"


def validar_totp(secreto, codigo):
    codigo = str(codigo or "").strip()
    ahora = time.time()
    return len(codigo) == 6 and any(
        hmac.compare_digest(codigo, codigo_totp(secreto, ahora + desfase * 30))
        for desfase in (-1, 0, 1)
    )


def emitir_verificacion(usuario, *, enviar=True):
    token = secrets.token_urlsafe(32)
    usuario.token_verificacion_hash = hashlib.sha256(token.encode()).hexdigest()
    usuario.token_verificacion_expira = utcnow() + timedelta(hours=24)
    db.session.commit()
    if enviar:
        enlace = url_for("autenticacion.verificar_correo", token=token, _external=True)
        mensaje = Message(
            subject="Verifica tu correo en NexuStock",
            recipients=[usuario.email],
            body=f"Confirma tu correo durante las próximas 24 horas:\n\n{enlace}",
        )
        try:
            correo.send(mensaje)
        except Exception as exc:
            current_app.logger.exception("No fue posible enviar la verificación de correo")
            raise ErrorEntregaCorreo(
                "La cuenta fue creada, pero el correo no pudo enviarse. "
                "Revisa la configuración SMTP y solicita un nuevo enlace."
            ) from exc
    return token


def confirmar_verificacion(token):
    hash_token = hashlib.sha256(str(token).encode()).hexdigest()
    usuario = db.session.scalar(
        db.select(Usuario).where(Usuario.token_verificacion_hash == hash_token)
    )
    if (
        not usuario
        or not usuario.token_verificacion_expira
        or usuario.token_verificacion_expira < utcnow()
    ):
        raise ErrorSeguridadCuenta("El enlace de verificación es inválido o expiró")
    usuario.email_verificado = True
    usuario.token_verificacion_hash = None
    usuario.token_verificacion_expira = None
    db.session.commit()
    return usuario


def iniciar_2fa(usuario):
    secreto = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    usuario.two_factor_secret_encrypted = _cifrar(secreto)
    usuario.two_factor_enabled = False
    db.session.commit()
    return secreto


def confirmar_2fa(usuario, codigo):
    if not usuario.two_factor_secret_encrypted:
        raise ErrorSeguridadCuenta("Primero debes iniciar la configuración")
    secreto = _descifrar(usuario.two_factor_secret_encrypted)
    if not validar_totp(secreto, codigo):
        raise ErrorSeguridadCuenta("Código de segundo factor inválido")
    usuario.two_factor_enabled = True
    usuario.version_sesion += 1
    registrar_auditoria(
        accion="usuario.2fa_activado",
        modulo="autenticacion",
        usuario_id=usuario.id,
        empresa_id=usuario.empresa_id,
        entidad_tipo="Usuario",
        entidad_id=usuario.id,
    )
    db.session.commit()


def verificar_2fa(usuario, codigo):
    return bool(
        usuario.two_factor_enabled
        and usuario.two_factor_secret_encrypted
        and validar_totp(_descifrar(usuario.two_factor_secret_encrypted), codigo)
    )


def desactivar_2fa(usuario, password, codigo):
    if not usuario.check_password(password) or not verificar_2fa(usuario, codigo):
        raise ErrorSeguridadCuenta("Contraseña o código inválido")
    usuario.two_factor_enabled = False
    usuario.two_factor_secret_encrypted = None
    usuario.version_sesion += 1
    db.session.commit()
