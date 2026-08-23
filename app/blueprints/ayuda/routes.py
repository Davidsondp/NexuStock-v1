from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...services.ayuda import ErrorAyuda, enviar_solicitud

ayuda_bp = Blueprint("ayuda", __name__, url_prefix="/ayuda")


@ayuda_bp.post("/contacto")
@login_required
def contacto():
    try:
        return jsonify(enviar_solicitud(current_user, **(request.get_json(silent=True) or {})))
    except (ErrorAyuda, TypeError) as exc:
        codigo = getattr(exc, "codigo", "solicitud_ayuda_invalida")
        return jsonify({"codigo": codigo, "mensaje": str(exc)}), 400
