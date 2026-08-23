from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.alertas import ErrorAlerta, ServicioAlertas

alertas_bp = Blueprint("alertas", __name__, url_prefix="/api/alertas")


def _serializar(alerta):
    return {
        "id": alerta.id,
        "producto_id": alerta.producto_id,
        "bodega_id": alerta.bodega_id,
        "lote_id": alerta.lote_id,
        "tipo": alerta.tipo,
        "estado": alerta.estado,
        "prioridad": alerta.prioridad,
        "titulo": alerta.titulo,
        "mensaje": alerta.mensaje,
        "datos": alerta.datos,
        "creado_en": (alerta.creado_en.isoformat()),
    }


@alertas_bp.get("")
@login_required
@requerir_permiso("alertas.ver")
def listar():
    servicio = ServicioAlertas(current_user)
    alertas = servicio.listar(
        estado=request.args.get("estado", "activa"),
        tipo=request.args.get("tipo"),
        bodega_id=request.args.get("bodega_id", type=int),
    )
    return jsonify({"alertas": [_serializar(a) for a in alertas]})


@alertas_bp.post("/generar")
@login_required
@requerir_permiso("alertas.gestionar")
def generar():
    resultado = ServicioAlertas(current_user).generar()
    return jsonify(
        {
            "creadas": resultado.creadas,
            "actualizadas": resultado.actualizadas,
            "resueltas": resultado.resueltas,
        }
    )


@alertas_bp.post("/<int:alerta_id>/resolver")
@login_required
@requerir_permiso("alertas.gestionar")
def resolver(alerta_id):
    try:
        return jsonify(
            _serializar(ServicioAlertas(current_user).cambiar_estado(alerta_id, "resuelta"))
        )
    except ErrorAlerta as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400


@alertas_bp.post("/<int:alerta_id>/ignorar")
@login_required
@requerir_permiso("alertas.gestionar")
def ignorar(alerta_id):
    try:
        return jsonify(
            _serializar(ServicioAlertas(current_user).cambiar_estado(alerta_id, "ignorada"))
        )
    except ErrorAlerta as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400
