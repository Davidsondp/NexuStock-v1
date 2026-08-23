from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from ...models import Cliente, Producto, db

from ...permisos import requerir_permiso
from ...services.ventas import ErrorVenta, ServicioVentas

ventas_bp = Blueprint("ventas", __name__, url_prefix="/api/ventas")


def _fecha_iso(valor):
    return valor.isoformat() if valor else None


def _serializar(venta):
    cliente = None

    if venta.cliente_id:
        cliente = db.session.get(
            Cliente,
            venta.cliente_id,
        )

    productos_ids = {item.producto_id for item in venta.items}

    productos = {}

    if productos_ids:
        productos = {
            producto.id: producto
            for producto in db.session.scalars(
                db.select(Producto).where(
                    Producto.id.in_(productos_ids),
                    Producto.empresa_id == venta.empresa_id,
                )
            )
        }

    return {
        "id": venta.id,
        "numero": venta.numero,
        "estado": venta.estado,
        "cliente_id": venta.cliente_id,
        "cliente_nombre": (cliente.nombre if cliente else None),
        "bodega_id": venta.bodega_id,
        "fecha_creacion": _fecha_iso(venta.creado_en),
        "confirmada_en": _fecha_iso(venta.confirmada_en),
        "cancelada_en": _fecha_iso(venta.cancelada_en),
        "motivo_cancelacion": venta.motivo_cancelacion,
        "moneda": venta.moneda,
        "subtotal": str(venta.subtotal),
        "descuento": str(venta.descuento),
        "impuesto": str(venta.impuesto),
        "total": str(venta.total),
        "observaciones": venta.observaciones,
        "items": [
            {
                "id": item.id,
                "producto_id": item.producto_id,
                "producto_codigo": (
                    productos[item.producto_id].codigo if item.producto_id in productos else None
                ),
                "producto_nombre": (
                    productos[item.producto_id].nombre if item.producto_id in productos else None
                ),
                "presentacion_id": item.presentacion_id,
                "presentacion_codigo": item.presentacion_codigo,
                "presentacion_nombre": item.presentacion_nombre,
                "presentacion_abreviatura": item.presentacion_abreviatura,
                "cantidad_presentacion": str(item.cantidad_presentacion),
                "factor_conversion": str(item.factor_conversion),
                "precio_presentacion": str(item.precio_presentacion),
                "cantidad": str(item.cantidad),
                "precio_unitario": str(item.precio_unitario),
                "descuento": str(item.descuento),
                "impuesto": str(item.impuesto),
                "total": str(item.total),
                "seriales": [serial.numero_serial for serial in item.seriales],
            }
            for item in venta.items
        ],
    }


def _error(e):
    return jsonify({"codigo": getattr(e, "codigo", "venta_invalida"), "mensaje": str(e)}), 400


@ventas_bp.get("")
@login_required
@requerir_permiso("ventas.ver")
def listar():
    return jsonify(
        {
            "ventas": [
                _serializar(v)
                for v in ServicioVentas(current_user).listar(request.args.get("estado"))
            ]
        }
    )


@ventas_bp.get("/<int:venta_id>")
@login_required
@requerir_permiso("ventas.ver")
def obtener(venta_id):
    return jsonify(_serializar(ServicioVentas(current_user).obtener(venta_id)))


@ventas_bp.post("")
@login_required
@requerir_permiso("ventas.crear")
def crear():
    try:
        d = request.get_json(silent=True) or {}
        permitidos = {
            k: d[k]
            for k in ("numero", "bodega_id", "items", "cliente_id", "moneda", "observaciones")
            if k in d
        }
        return jsonify(_serializar(ServicioVentas(current_user).crear(**permitidos))), 201
    except (ErrorVenta, TypeError, KeyError, ValueError) as e:
        return _error(e)


@ventas_bp.post("/<int:venta_id>/reservar")
@login_required
@requerir_permiso("ventas.reservar")
def reservar(venta_id):
    try:
        return jsonify(_serializar(ServicioVentas(current_user).reservar(venta_id)))
    except ErrorVenta as e:
        return _error(e)


@ventas_bp.post("/<int:venta_id>/confirmar")
@login_required
@requerir_permiso("ventas.confirmar")
def confirmar(venta_id):
    try:
        return jsonify(_serializar(ServicioVentas(current_user).confirmar(venta_id)))
    except ErrorVenta as e:
        return _error(e)


@ventas_bp.post("/<int:venta_id>/cancelar")
@login_required
@requerir_permiso("ventas.cancelar")
def cancelar(venta_id):
    try:
        return jsonify(
            _serializar(
                ServicioVentas(current_user).cancelar(
                    venta_id, (request.get_json(silent=True) or {}).get("motivo")
                )
            )
        )
    except ErrorVenta as e:
        return _error(e)
