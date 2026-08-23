from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.configuracion import ErrorConfiguracion, ServicioConfiguracion

configuracion_bp = Blueprint("configuracion", __name__, url_prefix="/api/configuracion")


def _error(exc):
    return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400


@configuracion_bp.get("")
@login_required
@requerir_permiso("configuracion.ver")
def obtener():
    return jsonify(ServicioConfiguracion(current_user).resumen())


@configuracion_bp.patch("/empresa")
@login_required
@requerir_permiso("empresa.editar")
def editar_empresa():
    try:
        servicio = ServicioConfiguracion(current_user)
        servicio.editar_empresa(**(request.get_json(silent=True) or {}))
        return jsonify(servicio.resumen())
    except (ErrorConfiguracion, TypeError, ValueError) as exc:
        return _error(exc)


@configuracion_bp.patch("/preferencias")
@login_required
@requerir_permiso("configuracion.editar")
def editar_preferencias():
    try:
        servicio = ServicioConfiguracion(current_user)
        servicio.editar_preferencias(**(request.get_json(silent=True) or {}))
        return jsonify(servicio.resumen())
    except (ErrorConfiguracion, TypeError, ValueError) as exc:
        return _error(exc)
