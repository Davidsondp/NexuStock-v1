from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.clientes import (
    ErrorCliente,
    ServicioClientes,
)

clientes_bp = Blueprint(
    "clientes",
    __name__,
    url_prefix="/api/clientes",
)


def _serializar(cliente):
    return {
        "id": cliente.id,
        "nombre": cliente.nombre,
        "identificacion_fiscal": cliente.identificacion_fiscal,
        "email": cliente.email,
        "telefono": cliente.telefono,
        "direccion": cliente.direccion,
        "activo": cliente.activo,
    }


def _error_cliente(exc):
    return (
        jsonify(
            {
                "codigo": "cliente_invalido",
                "mensaje": str(exc),
            }
        ),
        400,
    )


@clientes_bp.get("")
@login_required
@requerir_permiso("clientes.ver")
def listar():
    valor_inactivos = (
        request.args.get(
            "incluir_inactivos",
            "",
        )
        .strip()
        .lower()
    )

    incluir_inactivos = valor_inactivos in {
        "1",
        "true",
        "si",
        "yes",
    }

    clientes = ServicioClientes(current_user).listar(
        busqueda=request.args.get("buscar"),
        incluir_inactivos=incluir_inactivos,
    )

    return jsonify({"clientes": [_serializar(cliente) for cliente in clientes]})


@clientes_bp.post("")
@login_required
@requerir_permiso("clientes.crear")
def crear():
    try:
        cliente = ServicioClientes(current_user).crear(**(request.get_json(silent=True) or {}))

        return jsonify(_serializar(cliente)), 201
    except ErrorCliente as exc:
        return _error_cliente(exc)


@clientes_bp.patch("/<int:cliente_id>")
@login_required
@requerir_permiso("clientes.editar")
def editar(cliente_id):
    try:
        cliente = ServicioClientes(current_user).editar(
            cliente_id,
            **(request.get_json(silent=True) or {}),
        )

        return jsonify(_serializar(cliente))
    except ErrorCliente as exc:
        return _error_cliente(exc)


@clientes_bp.post("/<int:cliente_id>/desactivar")
@login_required
@requerir_permiso("clientes.eliminar")
def desactivar(cliente_id):
    cliente = ServicioClientes(current_user).desactivar(cliente_id)

    return jsonify(_serializar(cliente))


@clientes_bp.post("/<int:cliente_id>/reactivar")
@login_required
@requerir_permiso("clientes.eliminar")
def reactivar(cliente_id):
    cliente = ServicioClientes(current_user).reactivar(cliente_id)

    return jsonify(_serializar(cliente))


@clientes_bp.delete("/<int:cliente_id>")
@login_required
@requerir_permiso("clientes.eliminar")
def eliminar(cliente_id):
    try:
        ServicioClientes(current_user).eliminar_logicamente(cliente_id)

        return "", 204
    except ErrorCliente as exc:
        return (
            jsonify(
                {
                    "codigo": "cliente_con_historial",
                    "mensaje": str(exc),
                }
            ),
            409,
        )
