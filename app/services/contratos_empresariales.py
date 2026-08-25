"""Notificaciones de solicitudes del plan Empresarial."""

from flask import current_app, url_for
from flask_mail import Message

from ..extensions import correo


def _enviar(mensaje, *, descripcion):
    try:
        correo.send(mensaje)
        return True
    except Exception:
        current_app.logger.exception(
            "No fue posible enviar %s",
            descripcion,
        )
        return False


def notificar_solicitud_empresarial(solicitud):
    destino = current_app.config["COMERCIAL_EMAIL"]
    panel_url = url_for(
        "panel_superadministracion.inicio",
        _external=True,
    )

    cuerpo_comercial = (
        "Nueva solicitud de contrato Empresarial en NexuStock\n\n"
        f"Solicitud: {solicitud.id}\n"
        f"Empresa: {solicitud.empresa_nombre}\n"
        f"Contacto: {solicitud.contacto_nombre}\n"
        f"Correo: {solicitud.email}\n"
        f"Tel?fono: {solicitud.telefono or 'No informado'}\n"
        f"Productos estimados: {solicitud.productos_estimados}\n"
        f"Usuarios estimados: {solicitud.usuarios_estimados}\n\n"
        f"Mensaje:\n{solicitud.mensaje or 'Sin mensaje'}\n\n"
        f"Revisar en el panel Super Admin: {panel_url}\n"
    )

    aviso_comercial = _enviar(
        Message(
            subject=("[NexuStock comercial] " f"Nueva solicitud #{solicitud.id}"),
            recipients=[destino],
            reply_to=solicitud.email,
            body=cuerpo_comercial,
        ),
        descripcion="el aviso comercial",
    )

    cuerpo_contacto = (
        f"Hola {solicitud.contacto_nombre},\n\n"
        "Recibimos la solicitud de contrato Empresarial "
        f"para {solicitud.empresa_nombre}.\n\n"
        "Nuestro equipo revisar? la capacidad solicitada y "
        "se comunicar? contigo para organizar el alcance, "
        "la propuesta y el contrato.\n\n"
        "Enviar esta solicitud no activa cobros ni inicia "
        "de forma automatica el periodo de evaluacion.\n\n"
        f"N?mero de solicitud: {solicitud.id}\n\n"
        "Equipo comercial de NexuStock\n"
    )

    confirmacion_contacto = _enviar(
        Message(
            subject=("Recibimos tu solicitud empresarial " f"#{solicitud.id}"),
            recipients=[solicitud.email],
            body=cuerpo_contacto,
        ),
        descripcion="la confirmaci?n al contacto",
    )

    return {
        "aviso_comercial": aviso_comercial,
        "confirmacion_contacto": confirmacion_contacto,
    }
