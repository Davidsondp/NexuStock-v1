from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.claves_api import ErrorClaveApi, SCOPES, ServicioClavesApi

claves_api_bp = Blueprint("claves_api", __name__, url_prefix="/api/claves")


def _serializar(clave):
    return {
        "id": clave.id,
        "nombre": clave.nombre,
        "prefijo": clave.prefijo,
        "permisos": [k for k, habilitado in (clave.permisos or {}).items() if habilitado],
        "activa": clave.activa,
        "ultimo_uso": clave.ultimo_uso.isoformat() if clave.ultimo_uso else None,
        "expira_en": clave.expira_en.isoformat() if clave.expira_en else None,
        "creado_en": clave.creado_en.isoformat(),
    }


@claves_api_bp.get("")
@login_required
@requerir_permiso("api.gestionar")
def listar():
    return jsonify(
        {
            "claves": [_serializar(c) for c in ServicioClavesApi(current_user).listar()],
            "permisos_disponibles": sorted(SCOPES),
        }
    )


@claves_api_bp.post("")
@login_required
@requerir_permiso("api.gestionar")
def crear():
    try:
        clave, token = ServicioClavesApi(current_user).crear(
            **(request.get_json(silent=True) or {})
        )
        return jsonify({**_serializar(clave), "token": token}), 201
    except (ErrorClaveApi, TypeError) as exc:
        return jsonify({"codigo": "clave_api_invalida", "mensaje": str(exc)}), 400


@claves_api_bp.delete("/<int:clave_id>")
@login_required
@requerir_permiso("api.gestionar")
def revocar(clave_id):
    return jsonify(_serializar(ServicioClavesApi(current_user).revocar(clave_id)))
