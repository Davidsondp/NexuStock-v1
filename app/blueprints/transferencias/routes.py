from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...models import Bodega, Producto, db
from ...permisos import requerir_permiso
from ...services.transferencias import ErrorTransferencia, ServicioTransferencias

transferencias_bp = Blueprint("transferencias", __name__, url_prefix="/api/transferencias")


def _serializar(transferencia):
    bodegas = {
        b.id: b
        for b in db.session.scalars(
            db.select(Bodega).where(
                Bodega.id.in_([transferencia.bodega_origen_id, transferencia.bodega_destino_id]),
                Bodega.empresa_id == transferencia.empresa_id,
            )
        )
    }
    productos_ids = {item.producto_id for item in transferencia.items}
    productos = {
        p.id: p
        for p in db.session.scalars(
            db.select(Producto).where(
                Producto.id.in_(productos_ids), Producto.empresa_id == transferencia.empresa_id
            )
        )
    }
    return {
        "id": transferencia.id,
        "numero": transferencia.numero,
        "estado": transferencia.estado,
        "bodega_origen_id": transferencia.bodega_origen_id,
        "bodega_origen": bodegas[transferencia.bodega_origen_id].nombre,
        "bodega_destino_id": transferencia.bodega_destino_id,
        "bodega_destino": bodegas[transferencia.bodega_destino_id].nombre,
        "observaciones": transferencia.observaciones,
        "creado_en": transferencia.creado_en.isoformat(),
        "fecha_solicitud": (
            transferencia.fecha_solicitud.isoformat() if transferencia.fecha_solicitud else None
        ),
        "fecha_despacho": (
            transferencia.fecha_despacho.isoformat() if transferencia.fecha_despacho else None
        ),
        "fecha_recepcion": (
            transferencia.fecha_recepcion.isoformat() if transferencia.fecha_recepcion else None
        ),
        "items": [
            {
                "id": item.id,
                "producto_id": item.producto_id,
                "producto_codigo": productos[item.producto_id].codigo,
                "producto_nombre": productos[item.producto_id].nombre,
                "cantidad_solicitada": str(item.cantidad_solicitada),
                "cantidad_despachada": str(item.cantidad_despachada),
                "cantidad_recibida": str(item.cantidad_recibida),
                "diferencia": str(item.cantidad_despachada - item.cantidad_recibida),
                "seriales": [serial.numero_serial for serial in item.seriales],
            }
            for item in transferencia.items
        ],
    }


def _error(exc):
    return jsonify({"codigo": "transferencia_invalida", "mensaje": str(exc)}), 400


@transferencias_bp.get("")
@login_required
@requerir_permiso("transferencias.ver")
def listar():
    try:
        transferencias = ServicioTransferencias(current_user).listar(request.args.get("estado"))
        return jsonify({"transferencias": [_serializar(t) for t in transferencias]})
    except ErrorTransferencia as exc:
        return _error(exc)


@transferencias_bp.get("/<int:transferencia_id>")
@login_required
@requerir_permiso("transferencias.ver")
def obtener(transferencia_id):
    return jsonify(_serializar(ServicioTransferencias(current_user).obtener(transferencia_id)))


@transferencias_bp.post("")
@login_required
@requerir_permiso("transferencias.crear")
def crear():
    datos = request.get_json(silent=True) or {}
    try:
        transferencia = ServicioTransferencias(current_user).crear(
            numero=datos.get("numero"),
            bodega_origen_id=datos.get("bodega_origen_id"),
            bodega_destino_id=datos.get("bodega_destino_id"),
            items=datos.get("items") or [],
            observaciones=datos.get("observaciones"),
        )
        return jsonify(_serializar(transferencia)), 201
    except (ErrorTransferencia, KeyError, TypeError, ValueError) as exc:
        return _error(exc)


@transferencias_bp.post("/<int:transferencia_id>/solicitar")
@login_required
@requerir_permiso("transferencias.crear")
def solicitar(transferencia_id):
    try:
        return jsonify(
            _serializar(ServicioTransferencias(current_user).solicitar(transferencia_id))
        )
    except ErrorTransferencia as exc:
        return _error(exc)


def _cantidades(datos):
    return {int(item_id): Decimal(str(cantidad)) for item_id, cantidad in (datos or {}).items()}


@transferencias_bp.post("/<int:transferencia_id>/despachar")
@login_required
@requerir_permiso("transferencias.despachar")
def despachar(transferencia_id):
    try:
        datos = request.get_json(silent=True) or {}
        resultado = ServicioTransferencias(current_user).despachar(
            transferencia_id, _cantidades(datos.get("cantidades")) or None
        )
        return jsonify(_serializar(resultado))
    except (ErrorTransferencia, ValueError) as exc:
        return _error(exc)


@transferencias_bp.post("/<int:transferencia_id>/recibir")
@login_required
@requerir_permiso("transferencias.recibir")
def recibir(transferencia_id):
    try:
        datos = request.get_json(silent=True) or {}
        resultado = ServicioTransferencias(current_user).recibir(
            transferencia_id, _cantidades(datos.get("cantidades")) or None
        )
        return jsonify(_serializar(resultado))
    except (ErrorTransferencia, ValueError) as exc:
        return _error(exc)


@transferencias_bp.post("/<int:transferencia_id>/cancelar")
@login_required
@requerir_permiso("transferencias.crear")
def cancelar(transferencia_id):
    try:
        datos = request.get_json(silent=True) or {}
        return jsonify(
            _serializar(
                ServicioTransferencias(current_user).cancelar(
                    transferencia_id, (datos.get("motivo") or "Cancelada por el usuario").strip()
                )
            )
        )
    except ErrorTransferencia as exc:
        return _error(exc)
