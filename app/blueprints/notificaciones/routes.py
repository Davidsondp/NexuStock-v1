from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.notificaciones import ErrorNotificacion, ServicioNotificaciones

notificaciones_bp = Blueprint("notificaciones", __name__, url_prefix="/api/notificaciones")


def _serializar(n):
    return {
        "id": n.id,
        "tipo": n.tipo,
        "titulo": n.titulo,
        "mensaje": n.mensaje,
        "leida": n.leida,
        "leida_en": n.leida_en.isoformat() if n.leida_en else None,
        "referencia_tipo": n.referencia_tipo,
        "referencia_id": n.referencia_id,
        "creado_en": n.creado_en.isoformat(),
    }


@notificaciones_bp.get("")
@login_required
@requerir_permiso("dashboard.ver")
def listar():
    try:
        servicio = ServicioNotificaciones(current_user)
        datos = servicio.listar(
            solo_no_leidas=request.args.get("solo_no_leidas") == "true",
            limite=request.args.get("limite", 100),
        )
        return jsonify(
            {
                "notificaciones": [_serializar(n) for n in datos],
                "no_leidas": len(servicio.listar(solo_no_leidas=True, limite=500)),
            }
        )
    except ErrorNotificacion as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400


@notificaciones_bp.post("/<int:notificacion_id>/leer")
@login_required
@requerir_permiso("dashboard.ver")
def leer(notificacion_id):
    return jsonify(_serializar(ServicioNotificaciones(current_user).marcar_leida(notificacion_id)))


@notificaciones_bp.post("/leer-todas")
@login_required
@requerir_permiso("dashboard.ver")
def leer_todas():
    return jsonify({"actualizadas": ServicioNotificaciones(current_user).marcar_todas_leidas()})
