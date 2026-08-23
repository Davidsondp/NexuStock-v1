from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...models import Bodega, Producto, db
from ...permisos import requerir_permiso
from ...services.seriales import ErrorSerial, ServicioSeriales

seriales_bp = Blueprint("seriales", __name__, url_prefix="/api/seriales")


def _serializar(serial):
    producto = db.session.get(Producto, serial.producto_id)
    bodega = db.session.get(Bodega, serial.bodega_id)
    return {
        "id": serial.id,
        "numero_serial": serial.numero_serial,
        "estado": serial.estado,
        "producto_id": serial.producto_id,
        "producto_codigo": producto.codigo,
        "producto_nombre": producto.nombre,
        "bodega_id": serial.bodega_id,
        "bodega_nombre": bodega.nombre,
        "venta_item_id": serial.venta_item_id,
        "transferencia_item_id": serial.transferencia_item_id,
        "fecha_ingreso": serial.fecha_ingreso.isoformat(),
        "fecha_salida": serial.fecha_salida.isoformat() if serial.fecha_salida else None,
    }


@seriales_bp.get("")
@login_required
@requerir_permiso("stock.ver")
def listar():
    seriales = ServicioSeriales(current_user).listar(
        producto_id=request.args.get("producto_id", type=int),
        bodega_id=request.args.get("bodega_id", type=int),
        estado=request.args.get("estado"),
        buscar=request.args.get("buscar"),
    )
    return jsonify({"seriales": [_serializar(serial) for serial in seriales]})


@seriales_bp.patch("/<int:serial_id>/estado")
@login_required
@requerir_permiso("stock.ajuste")
def cambiar_estado(serial_id):
    try:
        estado = (request.get_json(silent=True) or {}).get("estado")
        return jsonify(
            _serializar(ServicioSeriales(current_user).cambiar_estado(serial_id, estado))
        )
    except ErrorSerial as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400
