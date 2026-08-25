"""Controles HTTP transversales y límites persistentes."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import hmac
import re
import secrets

from flask import current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from .models import LimiteSolicitud, db, utcnow

RUTAS_LIMITADAS = {
    "/autenticacion/ingresar": (10, 300),
    "/autenticacion/registro": (5, 3600),
    "/autenticacion/olvide-password": (5, 3600),
    "/autenticacion/segundo-factor": (8, 300),
    "/autenticacion/reenviar-verificacion": (5, 3600),
    "/empresarial/solicitar": (5, 3600),
}

RUTAS_EQUIVALENTES = {
    "/login": "/autenticacion/ingresar",
    "/registro": "/autenticacion/registro",
}

PREFIJOS_LIMITADOS = {
    "/webhooks/integraciones/": (120, 60),
    "/api/comercial/": (90, 60),
    "/suscripciones/checkout/": (10, 60),
}

ID_SOLICITUD = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def _respuesta(codigo, mensaje, estado):
    return (
        jsonify(
            {"codigo": codigo, "mensaje": mensaje, "id_solicitud": getattr(g, "id_solicitud", None)}
        ),
        estado,
    )


def _identidad_cliente():
    # remote_addr es seguro cuando el proxy de confianza configura REMOTE_ADDR.
    origen = request.remote_addr or "desconocido"
    secreto = current_app.config.get("LIMITE_SOLICITUDES_SECRET") or current_app.secret_key
    return hmac.new(str(secreto).encode(), origen.encode(), hashlib.sha256).hexdigest()


def _aplicar_limite():
    ruta_limite = RUTAS_EQUIVALENTES.get(
        request.path,
        request.path,
    )

    regla = RUTAS_LIMITADAS.get(ruta_limite)

    if regla is None:
        regla = next(
            (
                valor
                for prefijo, valor in PREFIJOS_LIMITADOS.items()
                if ruta_limite.startswith(prefijo)
            ),
            None,
        )

    if request.method != "POST" or not regla:
        return None

    maximo, segundos = regla
    ahora = utcnow()
    epoch = int(ahora.timestamp())
    inicio_epoch = epoch - (epoch % segundos)
    inicio = datetime.fromtimestamp(inicio_epoch)
    expira = inicio + timedelta(seconds=segundos)
    clave = _identidad_cliente()

    try:
        contador = db.session.scalar(
            db.select(LimiteSolicitud)
            .where(
                LimiteSolicitud.clave_hash == clave,
                LimiteSolicitud.ruta == ruta_limite,
                LimiteSolicitud.ventana_inicio == inicio,
            )
            .with_for_update()
        )

        if contador is None:
            contador = LimiteSolicitud(
                clave_hash=clave,
                ruta=ruta_limite,
                ventana_inicio=inicio,
                expira_en=expira,
                cantidad=1,
            )
            db.session.add(contador)
        else:
            contador.cantidad += 1

        db.session.commit()

    except IntegrityError:
        db.session.rollback()

        contador = db.session.scalar(
            db.select(LimiteSolicitud)
            .where(
                LimiteSolicitud.clave_hash == clave,
                LimiteSolicitud.ruta == ruta_limite,
                LimiteSolicitud.ventana_inicio == inicio,
            )
            .with_for_update()
        )

        contador.cantidad += 1
        db.session.commit()

    if contador.cantidad > maximo:
        respuesta = _respuesta(
            "demasiadas_solicitudes",
            "Demasiados intentos. Intenta m?s tarde.",
            429,
        )
        respuesta[0].headers["Retry-After"] = str(
            max(
                1,
                int((expira - ahora).total_seconds()),
            )
        )
        return respuesta

    return None


def registrar_seguridad(app):
    @app.before_request
    def validar_solicitud():
        recibido = request.headers.get("X-Request-ID")
        g.id_solicitud = (
            recibido if recibido and ID_SOLICITUD.fullmatch(recibido) else secrets.token_hex(16)
        )
        if (
            request.path.startswith("/api/")
            and request.method in {"POST", "PUT", "PATCH"}
            and request.content_length not in (None, 0)
        ):
            if not request.is_json:
                raise UnsupportedMediaType("La solicitud debe usar application/json")
            try:
                request.get_json()
            except BadRequest as exc:
                raise BadRequest("El cuerpo JSON no es válido") from exc
        return _aplicar_limite()

    @app.after_request
    def cabeceras_seguras(respuesta):
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        respuesta.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=(self)"
        respuesta.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' https: data:; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self' https://webpay3gint.transbank.cl https://webpay3g.transbank.cl; object-src 'none'"
        )
        respuesta.headers["X-Request-ID"] = getattr(g, "id_solicitud", secrets.token_hex(16))
        if request.endpoint != "static":
            respuesta.headers["Cache-Control"] = "no-store"
        if current_app.config.get("SESSION_COOKIE_SECURE"):
            respuesta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return respuesta

    @app.errorhandler(400)
    def solicitud_invalida(_exc):
        return _respuesta("solicitud_invalida", "La solicitud no es válida", 400)

    @app.errorhandler(404)
    def no_encontrado(_exc):
        return _respuesta("no_encontrado", "Recurso no encontrado", 404)

    @app.errorhandler(405)
    def metodo_no_permitido(_exc):
        return _respuesta("metodo_no_permitido", "Método no permitido", 405)

    @app.errorhandler(413)
    def contenido_grande(_exc):
        return _respuesta(
            "contenido_demasiado_grande", "El contenido supera el tamaño permitido", 413
        )

    @app.errorhandler(415)
    def tipo_no_admitido(_exc):
        return _respuesta("tipo_contenido_no_admitido", "Se requiere application/json", 415)

    @app.errorhandler(429)
    def limite_excedido(_exc):
        return _respuesta("demasiadas_solicitudes", "Demasiadas solicitudes", 429)

    @app.errorhandler(500)
    def error_interno(exc):
        db.session.rollback()
        current_app.logger.exception(
            "Error interno id_solicitud=%s", getattr(g, "id_solicitud", None), exc_info=exc
        )
        return _respuesta("error_interno", "Ocurrió un error interno", 500)
