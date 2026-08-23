"""Contacto seguro con el equipo de soporte."""

from datetime import timedelta

from flask import current_app
from flask_mail import Message

from ..extensions import correo
from ..models import Auditoria, db, utcnow
from .auditoria import registrar_auditoria


class ErrorAyuda(ValueError):
    codigo = "solicitud_ayuda_invalida"


CATEGORIAS = {
    "inventario": "Inventario y productos",
    "ventas": "Ventas y clientes",
    "compras": "Compras y proveedores",
    "importaciones": "Importación de documentos",
    "ia": "Nexu IA",
    "cuenta": "Cuenta y seguridad",
    "facturacion": "Planes y facturación",
    "otro": "Otro tema",
}


def enviar_solicitud(actor, *, categoria, asunto, mensaje, pagina=None):
    if not actor.is_authenticated:
        raise PermissionError("Debes iniciar sesión")
    categoria = str(categoria or "").strip().lower()
    asunto = " ".join(str(asunto or "").split())
    mensaje = str(mensaje or "").strip()
    pagina = str(pagina or "").strip()[:300] or None
    if categoria not in CATEGORIAS:
        raise ErrorAyuda("Selecciona una categoría válida")
    if not 5 <= len(asunto) <= 120:
        raise ErrorAyuda("El asunto debe tener entre 5 y 120 caracteres")
    if not 20 <= len(mensaje) <= 3000:
        raise ErrorAyuda("Describe el problema usando entre 20 y 3.000 caracteres")
    desde = utcnow() - timedelta(hours=1)
    recientes = db.session.scalar(
        db.select(db.func.count(Auditoria.id)).where(
            Auditoria.usuario_id == actor.id,
            Auditoria.accion == "soporte.solicitud",
            Auditoria.fecha >= desde,
        )
    )
    if recientes >= 5:
        raise ErrorAyuda("Alcanzaste el límite temporal de solicitudes; inténtalo más tarde")

    destino = current_app.config["SOPORTE_EMAIL"]
    empresa = actor.empresa.nombre if actor.empresa else "Ámbito global"
    cuerpo = (
        "Nueva solicitud desde el Centro de Ayuda de NexuStock\n\n"
        f"Categoría: {CATEGORIAS[categoria]}\n"
        f"Asunto: {asunto}\n"
        f"Usuario: {actor.nombre} {actor.apellido or ''} <{actor.email}>\n"
        f"Empresa: {empresa}\n"
        f"Rol: {actor.rol}\n"
        f"Página: {pagina or 'No informada'}\n\n"
        f"Mensaje:\n{mensaje}\n"
    )
    enviado = True
    try:
        correo.send(
            Message(
                subject=f"[NexuStock soporte] {asunto}",
                recipients=[destino],
                reply_to=actor.email,
                body=cuerpo,
            )
        )
    except Exception:
        enviado = False
        current_app.logger.exception("No fue posible enviar la solicitud de soporte")

    registrar_auditoria(
        accion="soporte.solicitud",
        modulo="ayuda",
        usuario_id=actor.id,
        empresa_id=actor.empresa_id,
        entidad_tipo="Soporte",
        descripcion=asunto,
        datos_nuevos={"categoria": categoria, "enviado": enviado},
    )
    db.session.commit()
    return {"enviado": enviado, "correo": destino}
