from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.ubicaciones import ErrorUbicacion, ServicioUbicaciones

ubicaciones_bp = Blueprint("ubicaciones", __name__, url_prefix="/api")


def _error(exc, estado=400):
    return jsonify({"codigo": "ubicacion_invalida", "mensaje": str(exc)}), estado


def _sucursal(s):
    return {
        "id": s.id,
        "codigo": s.codigo,
        "nombre": s.nombre,
        "direccion": s.direccion,
        "ciudad": s.ciudad,
        "telefono": s.telefono,
        "activa": s.activa,
    }


def _bodega(b):
    return {
        "id": b.id,
        "sucursal_id": b.sucursal_id,
        "codigo": b.codigo,
        "nombre": b.nombre,
        "descripcion": b.descripcion,
        "activa": b.activa,
    }


@ubicaciones_bp.get("/sucursales")
@login_required
@requerir_permiso("sucursales.ver")
def listar_sucursales():
    incluir = (
        request.args.get(
            "incluir_inactivas",
            "false",
        ).lower()
        == "true"
    )
    sucursales = ServicioUbicaciones(current_user).listar_sucursales(incluir_inactivas=incluir)
    return jsonify({"sucursales": [_sucursal(sucursal) for sucursal in sucursales]})


@ubicaciones_bp.post("/sucursales")
@login_required
@requerir_permiso("sucursales.crear")
def crear_sucursal():
    try:
        recibidos = request.get_json(silent=True) or {}
        permitidos = {
            campo: recibidos[campo]
            for campo in (
                "codigo",
                "nombre",
                "direccion",
                "ciudad",
                "telefono",
                "crear_bodega_principal",
            )
            if campo in recibidos
        }
        sucursal = ServicioUbicaciones(current_user).crear_sucursal(**permitidos)
        return jsonify(_sucursal(sucursal)), 201
    except ErrorUbicacion as exc:
        return _error(exc)


@ubicaciones_bp.patch("/sucursales/<int:sucursal_id>")
@login_required
@requerir_permiso("sucursales.editar")
def editar_sucursal(sucursal_id):
    try:
        datos = request.get_json(silent=True) or {}
        permitidos = {
            campo: datos[campo]
            for campo in (
                "codigo",
                "nombre",
                "direccion",
                "ciudad",
                "telefono",
            )
            if campo in datos
        }
        sucursal = ServicioUbicaciones(current_user).editar_sucursal(
            sucursal_id,
            **permitidos,
        )
        return jsonify(_sucursal(sucursal))
    except (
        ErrorUbicacion,
        TypeError,
        ValueError,
    ) as exc:
        return _error(exc)


@ubicaciones_bp.post("/sucursales/<int:sucursal_id>/reactivar")
@login_required
@requerir_permiso("sucursales.editar")
def reactivar_sucursal(sucursal_id):
    try:
        sucursal = ServicioUbicaciones(current_user).reactivar_sucursal(sucursal_id)
        return jsonify(_sucursal(sucursal))
    except ErrorUbicacion as exc:
        return _error(exc, 409)


@ubicaciones_bp.delete("/sucursales/<int:sucursal_id>")
@login_required
@requerir_permiso("sucursales.desactivar")
def desactivar_sucursal(sucursal_id):
    try:
        ServicioUbicaciones(current_user).desactivar_sucursal(sucursal_id)
        return "", 204
    except ErrorUbicacion as exc:
        return _error(exc, 409)


@ubicaciones_bp.get("/bodegas")
@login_required
@requerir_permiso("bodegas.ver")
def listar_bodegas():
    sucursal_id = request.args.get(
        "sucursal_id",
        type=int,
    )
    incluir = (
        request.args.get(
            "incluir_inactivas",
            "false",
        ).lower()
        == "true"
    )
    bodegas = ServicioUbicaciones(current_user).listar_bodegas(
        sucursal_id=sucursal_id,
        incluir_inactivas=incluir,
    )
    return jsonify({"bodegas": [_bodega(bodega) for bodega in bodegas]})


@ubicaciones_bp.post("/bodegas")
@login_required
@requerir_permiso("bodegas.crear")
def crear_bodega():
    try:
        recibidos = request.get_json(silent=True) or {}
        permitidos = {
            campo: recibidos[campo]
            for campo in ("sucursal_id", "codigo", "nombre", "descripcion")
            if campo in recibidos
        }
        bodega = ServicioUbicaciones(current_user).crear_bodega(**permitidos)
        return jsonify(_bodega(bodega)), 201
    except ErrorUbicacion as exc:
        return _error(exc)


@ubicaciones_bp.patch("/bodegas/<int:bodega_id>")
@login_required
@requerir_permiso("bodegas.editar")
def editar_bodega(bodega_id):
    try:
        datos = request.get_json(silent=True) or {}
        permitidos = {
            campo: datos[campo]
            for campo in (
                "codigo",
                "nombre",
                "descripcion",
            )
            if campo in datos
        }
        bodega = ServicioUbicaciones(current_user).editar_bodega(
            bodega_id,
            **permitidos,
        )
        return jsonify(_bodega(bodega))
    except (
        ErrorUbicacion,
        TypeError,
        ValueError,
    ) as exc:
        return _error(exc)


@ubicaciones_bp.post("/bodegas/<int:bodega_id>/reactivar")
@login_required
@requerir_permiso("bodegas.editar")
def reactivar_bodega(bodega_id):
    try:
        bodega = ServicioUbicaciones(current_user).reactivar_bodega(bodega_id)
        return jsonify(_bodega(bodega))
    except ErrorUbicacion as exc:
        return _error(exc, 409)


@ubicaciones_bp.delete("/bodegas/<int:bodega_id>")
@login_required
@requerir_permiso("bodegas.desactivar")
def desactivar_bodega(bodega_id):
    try:
        ServicioUbicaciones(current_user).desactivar_bodega(bodega_id)
        return "", 204
    except ErrorUbicacion as exc:
        return _error(exc, 409)


@ubicaciones_bp.post("/sucursales/<int:sucursal_id>/usuarios/<int:usuario_id>")
@login_required
@requerir_permiso("usuarios.editar")
def asignar_usuario(sucursal_id, usuario_id):
    datos = request.get_json(silent=True) or {}
    asignacion = ServicioUbicaciones(current_user).asignar_usuario(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        es_principal=datos.get("es_principal", False),
    )
    return (
        jsonify(
            {
                "id": asignacion.id,
                "usuario_id": asignacion.usuario_id,
                "sucursal_id": asignacion.sucursal_id,
                "es_principal": asignacion.es_principal,
            }
        ),
        201,
    )


@ubicaciones_bp.delete("/sucursales/<int:sucursal_id>" "/usuarios/<int:usuario_id>")
@login_required
@requerir_permiso("usuarios.editar")
def desasignar_usuario(
    sucursal_id,
    usuario_id,
):
    try:
        ServicioUbicaciones(current_user).desasignar_usuario(
            usuario_id=usuario_id,
            sucursal_id=sucursal_id,
        )
        return "", 204
    except ErrorUbicacion as exc:
        return _error(exc, 409)
