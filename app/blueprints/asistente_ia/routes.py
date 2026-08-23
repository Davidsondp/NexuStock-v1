from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.asistente_ia import ErrorAsistenteIA, MODOS, ServicioAsistenteIA

asistente_ia_bp = Blueprint("asistente_ia", __name__, url_prefix="/api/ia")


def _serializar(interaccion):
    return {
        "id": interaccion.id,
        "conversacion_id": interaccion.conversacion_id,
        "modo": interaccion.modo,
        "pregunta": interaccion.pregunta,
        "respuesta": interaccion.respuesta,
        "proveedor": interaccion.proveedor,
        "modelo": interaccion.modelo,
        "latencia_ms": interaccion.latencia_ms,
        "valoracion": interaccion.valoracion,
        "creado_en": interaccion.creado_en.isoformat(),
    }


@asistente_ia_bp.get("")
@login_required
@requerir_permiso("ia.ver")
def historial():
    servicio = ServicioAsistenteIA(current_user)
    return jsonify(
        {
            "interacciones": [
                _serializar(i) for i in servicio.historial(request.args.get("limite", 30))
            ],
            "modos": sorted(MODOS),
        }
    )


@asistente_ia_bp.post("/consultar")
@login_required
@requerir_permiso("ia.ver")
def consultar():
    try:
        interaccion = ServicioAsistenteIA(current_user).consultar(
            **(request.get_json(silent=True) or {})
        )
        return jsonify(_serializar(interaccion)), 201
    except (ErrorAsistenteIA, TypeError) as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400


@asistente_ia_bp.post("/briefing")
@login_required
@requerir_permiso("ia.ver")
def briefing():
    try:
        return jsonify(_serializar(ServicioAsistenteIA(current_user).briefing())), 201
    except ErrorAsistenteIA as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400


@asistente_ia_bp.post("/<int:interaccion_id>/valorar")
@login_required
@requerir_permiso("ia.ver")
def valorar(interaccion_id):
    try:
        valoracion = (request.get_json(silent=True) or {}).get("valoracion")
        interaccion = ServicioAsistenteIA(current_user).valorar(interaccion_id, valoracion)
        return jsonify(_serializar(interaccion))
    except ErrorAsistenteIA as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400
