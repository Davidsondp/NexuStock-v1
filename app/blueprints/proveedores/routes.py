from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.proveedores import ErrorProveedor, ServicioProveedores

proveedores_bp = Blueprint("proveedores", __name__, url_prefix="/api/proveedores")


def _serializar(proveedor):
    return {
        "id": proveedor.id,
        "nombre": proveedor.nombre,
        "identificacion_fiscal": proveedor.identificacion_fiscal,
        "email": proveedor.email,
        "telefono": proveedor.telefono,
        "direccion": proveedor.direccion,
        "ciudad": proveedor.ciudad,
        "pais": proveedor.pais,
        "sitio_web": proveedor.sitio_web,
        "condiciones_pago": proveedor.condiciones_pago,
        "dias_entrega": proveedor.dias_entrega,
        "compra_minima": str(proveedor.compra_minima),
        "observaciones": proveedor.observaciones,
        "activo": proveedor.activo,
    }


@proveedores_bp.get("")
@login_required
@requerir_permiso("proveedores.ver")
def listar():
    valor_inactivos = request.args.get("incluir_inactivos", "").strip().lower()

    incluir_inactivos = valor_inactivos in {
        "1",
        "true",
        "si",
        "yes",
    }

    proveedores = ServicioProveedores(current_user).listar(
        busqueda=request.args.get("buscar"),
        incluir_inactivos=incluir_inactivos,
    )

    return jsonify({"proveedores": [_serializar(proveedor) for proveedor in proveedores]})


@proveedores_bp.post("")
@login_required
@requerir_permiso("proveedores.crear")
def crear():
    try:
        proveedor = ServicioProveedores(current_user).crear(**(request.get_json(silent=True) or {}))
        return jsonify(_serializar(proveedor)), 201
    except ErrorProveedor as exc:
        return jsonify({"codigo": "proveedor_invalido", "mensaje": str(exc)}), 400


@proveedores_bp.patch("/<int:proveedor_id>")
@login_required
@requerir_permiso("proveedores.editar")
def editar(proveedor_id):
    try:
        proveedor = ServicioProveedores(current_user).editar(
            proveedor_id, **(request.get_json(silent=True) or {})
        )
        return jsonify(_serializar(proveedor))
    except ErrorProveedor as exc:
        return jsonify({"codigo": "proveedor_invalido", "mensaje": str(exc)}), 400


@proveedores_bp.post("/<int:proveedor_id>/desactivar")
@login_required
@requerir_permiso("proveedores.eliminar")
def desactivar(proveedor_id):
    proveedor = ServicioProveedores(current_user).desactivar(proveedor_id)

    return jsonify(_serializar(proveedor))


@proveedores_bp.post("/<int:proveedor_id>/reactivar")
@login_required
@requerir_permiso("proveedores.eliminar")
def reactivar(proveedor_id):
    proveedor = ServicioProveedores(current_user).reactivar(proveedor_id)

    return jsonify(_serializar(proveedor))


@proveedores_bp.delete("/<int:proveedor_id>")
@login_required
@requerir_permiso("proveedores.eliminar")
def eliminar(proveedor_id):
    try:
        ServicioProveedores(current_user).eliminar_logicamente(proveedor_id)
        return "", 204
    except ErrorProveedor as exc:
        return jsonify({"codigo": "proveedor_con_historial", "mensaje": str(exc)}), 409
