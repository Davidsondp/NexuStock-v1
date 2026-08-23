from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.contexto import obtener_contexto
from ...services.importaciones import ErrorImportacion, ServicioImportaciones

importaciones_bp = Blueprint("importaciones", __name__, url_prefix="/importaciones")


def _servicio():
    contexto = obtener_contexto(current_user, crear_automaticamente=False)
    if not contexto:
        raise ErrorImportacion("Selecciona una sucursal y bodega antes de importar")
    return ServicioImportaciones(current_user, contexto)


@importaciones_bp.post("/previsualizar")
@login_required
@requerir_permiso("productos.importar")
def previsualizar():
    try:
        return jsonify(_servicio().previsualizar(request.files.get("archivo")))
    except ErrorImportacion as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400


@importaciones_bp.post("/confirmar")
@login_required
@requerir_permiso("productos.importar")
def confirmar():
    try:
        token = (request.get_json(silent=True) or {}).get("token")
        return jsonify(_servicio().confirmar(token))
    except ErrorImportacion as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400
