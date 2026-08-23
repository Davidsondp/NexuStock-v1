from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.compras import ErrorCompra, ServicioCompras

compras_bp = Blueprint("compras", __name__, url_prefix="/api/compras")


def _fecha_iso(valor):
    return valor.isoformat() if valor else None


def _orden(orden):
    return {
        "id": orden.id,
        "numero": orden.numero,
        "estado": orden.estado,
        "proveedor_id": orden.proveedor_id,
        "proveedor_nombre": (orden.proveedor.nombre if orden.proveedor else None),
        "bodega_destino_id": orden.bodega_destino_id,
        "fecha_orden": _fecha_iso(orden.fecha_orden),
        "fecha_entrega_esperada": _fecha_iso(orden.fecha_entrega_esperada),
        "moneda": orden.moneda,
        "subtotal": str(orden.subtotal),
        "descuento": str(orden.descuento),
        "impuesto": str(orden.impuesto),
        "total": str(orden.total),
        "observaciones": orden.observaciones,
        "cancelada_en": _fecha_iso(orden.cancelada_en),
        "motivo_cancelacion": orden.motivo_cancelacion,
        "items": [
            {
                "id": item.id,
                "producto_id": item.producto_id,
                "producto_codigo": (item.producto.codigo if item.producto else None),
                "producto_nombre": (item.producto.nombre if item.producto else None),
                "cantidad": str(item.cantidad),
                "cantidad_recibida": str(item.cantidad_recibida),
                "presentacion_id": item.presentacion_id,
                "presentacion_codigo": item.presentacion_codigo,
                "presentacion_nombre": item.presentacion_nombre,
                "presentacion_abreviatura": item.presentacion_abreviatura,
                "cantidad_presentacion": str(item.cantidad_presentacion),
                "factor_conversion": str(item.factor_conversion),
                "precio_presentacion": str(item.precio_presentacion),
                "precio_unitario": str(item.precio_unitario),
                "descuento": str(item.descuento),
                "impuesto": str(item.impuesto),
                "total": str(item.total),
            }
            for item in orden.items
        ],
    }


def _recepcion(recepcion):
    return {
        "id": recepcion.id,
        "numero": recepcion.numero,
        "estado": recepcion.estado,
        "orden_id": recepcion.orden_id,
        "bodega_id": recepcion.bodega_id,
        "fecha": _fecha_iso(recepcion.fecha),
        "documento_referencia": recepcion.documento_referencia,
        "observaciones": recepcion.observaciones,
        "items": [
            {
                "id": item.id,
                "orden_item_id": item.orden_item_id,
                "cantidad": str(item.cantidad),
                "cantidad_presentacion": str(item.cantidad_presentacion),
                "factor_conversion": str(item.factor_conversion),
                "costo_unitario": str(item.costo_unitario),
                "costo_presentacion": str(item.costo_presentacion),
                "numero_lote": item.numero_lote,
                "fecha_vencimiento": _fecha_iso(item.fecha_vencimiento),
            }
            for item in recepcion.items
        ],
        "orden": _orden(recepcion.orden),
    }


def _error(exc):
    return jsonify({"codigo": getattr(exc, "codigo", "compra_invalida"), "mensaje": str(exc)}), 400


@compras_bp.get("")
@login_required
@requerir_permiso("compras.ver")
def listar():
    ordenes = ServicioCompras(current_user).listar(estado=request.args.get("estado"))
    return jsonify({"ordenes": [_orden(o) for o in ordenes]})


@compras_bp.get("/<int:orden_id>")
@login_required
@requerir_permiso("compras.ver")
def obtener(orden_id):
    return jsonify(_orden(ServicioCompras(current_user).obtener(orden_id)))


@compras_bp.post("")
@login_required
@requerir_permiso("compras.crear")
def crear():
    try:
        datos = request.get_json(silent=True) or {}
        permitidos = {
            k: datos[k]
            for k in (
                "numero",
                "proveedor_id",
                "bodega_destino_id",
                "items",
                "moneda",
                "fecha_entrega_esperada",
                "observaciones",
            )
            if k in datos
        }
        return jsonify(_orden(ServicioCompras(current_user).crear(**permitidos))), 201
    except (ErrorCompra, TypeError, KeyError, ValueError) as exc:
        return _error(exc)


@compras_bp.patch("/<int:orden_id>")
@login_required
@requerir_permiso("compras.editar")
def editar(orden_id):
    try:
        datos = request.get_json(silent=True) or {}

        permitidos = {
            clave: datos[clave]
            for clave in (
                "numero",
                "proveedor_id",
                "bodega_destino_id",
                "items",
                "moneda",
                "fecha_entrega_esperada",
                "observaciones",
            )
            if clave in datos
        }

        orden = ServicioCompras(current_user).editar(
            orden_id,
            **permitidos,
        )

        return jsonify(_orden(orden))
    except (
        ErrorCompra,
        TypeError,
        KeyError,
        ValueError,
    ) as exc:
        return _error(exc)


@compras_bp.post("/<int:orden_id>/confirmar")
@login_required
@requerir_permiso("compras.crear")
def confirmar(orden_id):
    try:
        return jsonify(_orden(ServicioCompras(current_user).confirmar(orden_id)))
    except ErrorCompra as exc:
        return _error(exc)


@compras_bp.post("/<int:orden_id>/enviar")
@login_required
@requerir_permiso("compras.enviar")
def enviar(orden_id):
    try:
        return jsonify(_orden(ServicioCompras(current_user).enviar(orden_id)))
    except ErrorCompra as exc:
        return _error(exc)


@compras_bp.post("/<int:orden_id>/cancelar")
@login_required
@requerir_permiso("compras.cancelar")
def cancelar(orden_id):
    try:
        orden = ServicioCompras(current_user).cancelar(
            orden_id, (request.get_json(silent=True) or {}).get("motivo")
        )
        return jsonify(_orden(orden))
    except ErrorCompra as exc:
        return _error(exc)


@compras_bp.post("/<int:orden_id>/recepciones")
@login_required
@requerir_permiso("compras.recibir")
def recibir(orden_id):
    try:
        datos = request.get_json(silent=True) or {}
        permitidos = {
            k: datos[k]
            for k in ("numero", "items", "documento_referencia", "observaciones")
            if k in datos
        }
        recepcion = ServicioCompras(current_user).recibir(orden_id, **permitidos)
        return jsonify(_recepcion(recepcion)), 201
    except (ErrorCompra, TypeError, KeyError, ValueError) as exc:
        return _error(exc)
