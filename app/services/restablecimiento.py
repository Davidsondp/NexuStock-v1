from flask import current_app, url_for
from flask_mail import Message

from ..extensions import correo
from ..models import Usuario, db
from .auditoria import registrar_auditoria


def solicitar_restablecimiento(email: str) -> None:
    """Genera y envía el token sin revelar al llamador si el usuario existe."""
    usuario = db.session.scalar(db.select(Usuario).where(Usuario.email == email.strip().lower()))
    if not usuario or not usuario.activo or usuario.eliminado:
        return
    token = usuario.crear_token_restablecimiento()
    registrar_auditoria(
        accion="password.restablecimiento_solicitado",
        modulo="autenticacion",
        usuario_id=usuario.id,
        empresa_id=usuario.empresa_id,
        entidad_tipo="Usuario",
        entidad_id=usuario.id,
    )
    db.session.commit()
    enlace = url_for("autenticacion.restablecer_password_route", token=token, _external=True)
    mensaje = Message(
        subject="Restablece tu contraseña de NexuStock",
        recipients=[usuario.email],
        body=(
            "Solicitaste cambiar tu contraseña de NexuStock.\n\n"
            f"Usa este enlace durante los próximos 30 minutos:\n{enlace}\n\n"
            "Si no realizaste esta solicitud, ignora este mensaje."
        ),
    )
    try:
        correo.send(mensaje)
    except Exception:
        current_app.logger.exception("No fue posible enviar el correo de restablecimiento")


def buscar_usuario_por_token(token: str) -> Usuario | None:
    import hashlib

    resumen = hashlib.sha256((token or "").encode("utf-8")).hexdigest()
    usuario = db.session.scalar(
        db.select(Usuario).where(Usuario.token_restablecimiento_hash == resumen)
    )
    return usuario if usuario and usuario.token_restablecimiento_valido(token) else None


def restablecer_password(usuario: Usuario, token: str, password: str) -> bool:
    if not usuario.token_restablecimiento_valido(token):
        return False
    usuario.consumir_token_restablecimiento(password)
    registrar_auditoria(
        accion="password.restablecido",
        modulo="autenticacion",
        usuario_id=usuario.id,
        empresa_id=usuario.empresa_id,
        entidad_tipo="Usuario",
        entidad_id=usuario.id,
    )
    db.session.commit()
    return True
