import csv
import io
import json

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from ...models import Usuario, db
from ...permisos import requerir_permiso
from ...services.auditoria import ErrorAuditoria, ServicioAuditoriaEmpresa

auditoria_bp = Blueprint("auditoria", __name__, url_prefix="/api/auditoria")


def _serializar(registro):
    usuario = db.session.get(Usuario, registro.usuario_id) if registro.usuario_id else None
    return {
        "id": registro.id,
        "fecha": registro.fecha.isoformat(),
        "usuario_id": registro.usuario_id,
        "usuario": (f"{usuario.nombre} {usuario.apellido or ''}".strip() if usuario else "Sistema"),
        "accion": registro.accion,
        "modulo": registro.modulo,
        "entidad_tipo": registro.entidad_tipo,
        "entidad_id": registro.entidad_id,
        "descripcion": registro.descripcion,
        "datos_anteriores": registro.datos_anteriores,
        "datos_nuevos": registro.datos_nuevos,
        "ip": registro.ip,
        "id_solicitud": registro.id_solicitud,
    }


def _filtros():
    return {
        "modulo": request.args.get("modulo"),
        "accion": request.args.get("accion"),
        "usuario_id": request.args.get("usuario_id", type=int),
        "desde": request.args.get("desde"),
        "hasta": request.args.get("hasta"),
        "buscar": request.args.get("buscar"),
        "limite": request.args.get("limite", 200),
    }


@auditoria_bp.get("")
@login_required
@requerir_permiso("auditoria.ver")
def listar():
    try:
        servicio = ServicioAuditoriaEmpresa(current_user)
        return jsonify(
            {
                "auditoria": [_serializar(r) for r in servicio.listar(**_filtros())],
                "usuarios": [
                    {"id": u.id, "nombre": f"{u.nombre} {u.apellido or ''}".strip()}
                    for u in servicio.usuarios()
                ],
            }
        )
    except ErrorAuditoria as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400


@auditoria_bp.get("/exportar.csv")
@login_required
@requerir_permiso("auditoria.ver")
def exportar():
    try:
        registros = ServicioAuditoriaEmpresa(current_user).listar(**_filtros())
    except ErrorAuditoria as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";")
    escritor.writerow(["Fecha UTC", "Usuario", "Módulo", "Acción", "Entidad", "ID", "Datos"])
    for registro in registros:
        datos = _serializar(registro)
        escritor.writerow(
            [
                datos["fecha"],
                datos["usuario"],
                datos["modulo"],
                datos["accion"],
                datos["entidad_tipo"],
                datos["entidad_id"],
                json.dumps(datos["datos_nuevos"], ensure_ascii=False),
            ]
        )
    return Response(
        "\ufeff" + salida.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=nexustock_auditoria.csv"},
    )
