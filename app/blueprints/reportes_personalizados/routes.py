from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.reportes_personalizados import (
    ErrorReportePersonalizado,
    ServicioReportesPersonalizados,
    TIPOS,
)

reportes_personalizados_bp = Blueprint(
    "reportes_personalizados", __name__, url_prefix="/api/reportes-personalizados"
)


def _serializar(reporte):
    return {
        "id": reporte.id,
        "nombre": reporte.nombre,
        "tipo": reporte.tipo,
        "configuracion": reporte.configuracion,
    }


@reportes_personalizados_bp.get("")
@login_required
@requerir_permiso("reportes.personalizados")
def listar():
    return jsonify(
        {
            "reportes": [
                _serializar(r) for r in ServicioReportesPersonalizados(current_user).listar()
            ],
            "tipos": sorted(TIPOS),
        }
    )


@reportes_personalizados_bp.post("")
@login_required
@requerir_permiso("reportes.personalizados")
def crear():
    try:
        reporte = ServicioReportesPersonalizados(current_user).crear(
            **(request.get_json(silent=True) or {})
        )
        return jsonify(_serializar(reporte)), 201
    except (ErrorReportePersonalizado, TypeError) as exc:
        return jsonify({"codigo": "reporte_personalizado_invalido", "mensaje": str(exc)}), 400


@reportes_personalizados_bp.get("/<int:reporte_id>/ejecutar")
@login_required
@requerir_permiso("reportes.personalizados")
def ejecutar(reporte_id):
    datos = ServicioReportesPersonalizados(current_user).ejecutar(
        reporte_id, desde=request.args.get("desde"), hasta=request.args.get("hasta")
    )
    return jsonify({"datos": datos})


@reportes_personalizados_bp.delete("/<int:reporte_id>")
@login_required
@requerir_permiso("reportes.personalizados")
def eliminar(reporte_id):
    ServicioReportesPersonalizados(current_user).eliminar(reporte_id)
    return "", 204
