from datetime import date

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...models import (
    Inventario,
    Lote,
    Movimiento,
    Producto,
    db,
)
from ...services.perfiles_empresa import tiene_capacidad
from ...permisos import requerir_permiso
from ...services.contexto import (
    obtener_contexto,
    requerir_contexto,
)
from ...services.inventario import (
    ErrorInventario,
    ServicioInventario,
)

inventario_bp = Blueprint(
    "inventario",
    __name__,
    url_prefix="/api/inventario",
)


def _serializar_resultado(resultado, tipo):
    return {
        "tipo": tipo,
        "inventario_id": resultado.inventario_id,
        "movimiento_id": resultado.movimiento_id,
        "stock_anterior": format(
            resultado.stock_anterior,
            ".3f",
        ),
        "stock_nuevo": format(
            resultado.stock_nuevo,
            ".3f",
        ),
        "costo_promedio": format(
            resultado.costo_promedio,
            ".4f",
        ),
    }


def _error(exc, codigo=None):
    return (
        jsonify(
            {
                "codigo": (
                    codigo
                    or getattr(
                        exc,
                        "codigo",
                        "error_inventario",
                    )
                ),
                "mensaje": str(exc),
            }
        ),
        400,
    )


def _serializar_stock(
    inventario,
    producto,
    bodega,
):
    cantidad = inventario.cantidad
    reservada = inventario.cantidad_reservada
    disponible = inventario.cantidad_disponible
    costo_promedio = inventario.costo_promedio
    valor = cantidad * costo_promedio

    return {
        "inventario_id": inventario.id,
        "producto_id": producto.id,
        "producto_codigo": producto.codigo,
        "producto_nombre": producto.nombre,
        "bodega_id": bodega.id,
        "bodega_nombre": bodega.nombre,
        "cantidad": format(cantidad, ".3f"),
        "reservada": format(reservada, ".3f"),
        "disponible": format(
            disponible,
            ".3f",
        ),
        "costo_promedio": format(
            costo_promedio,
            ".4f",
        ),
        "valor": format(valor, ".2f"),
    }


def _serializar_movimiento(
    movimiento,
    producto,
):
    return {
        "id": movimiento.id,
        "producto_id": producto.id,
        "producto_codigo": producto.codigo,
        "producto_nombre": producto.nombre,
        "bodega_id": movimiento.bodega_id,
        "tipo": movimiento.tipo,
        "subtipo": movimiento.subtipo,
        "cantidad": format(
            movimiento.cantidad,
            ".3f",
        ),
        "stock_anterior": format(
            movimiento.stock_anterior,
            ".3f",
        ),
        "stock_nuevo": format(
            movimiento.stock_nuevo,
            ".3f",
        ),
        "costo_unitario": (
            format(
                movimiento.costo_unitario,
                ".4f",
            )
            if movimiento.costo_unitario is not None
            else None
        ),
        "precio_unitario": (
            format(
                movimiento.precio_unitario,
                ".2f",
            )
            if movimiento.precio_unitario is not None
            else None
        ),
        "referencia_tipo": movimiento.referencia_tipo,
        "referencia_id": movimiento.referencia_id,
        "motivo": movimiento.motivo,
        "fecha": movimiento.fecha.isoformat(),
    }


def _contexto_actual():
    contexto = obtener_contexto(
        current_user,
        crear_automaticamente=False,
    )

    if not contexto:
        raise ValueError("No existe un contexto operativo válido")

    return contexto


def _estado_vencimiento(fecha_vencimiento):
    if fecha_vencimiento is None:
        return "sin_vencimiento", None

    dias = (fecha_vencimiento - date.today()).days

    if dias < 0:
        estado = "vencido"
    elif dias == 0:
        estado = "vence_hoy"
    elif dias <= 30:
        estado = "proximo_vencer"
    else:
        estado = "vigente"

    return estado, dias


def _serializar_lote(lote, producto):
    estado, dias = _estado_vencimiento(lote.fecha_vencimiento)
    valor = lote.cantidad * lote.costo_unitario

    return {
        "id": lote.id,
        "producto_id": producto.id,
        "producto_codigo": producto.codigo,
        "producto_nombre": producto.nombre,
        "bodega_id": lote.bodega_id,
        "numero": lote.numero,
        "fecha_fabricacion": (
            lote.fecha_fabricacion.isoformat() if lote.fecha_fabricacion else None
        ),
        "fecha_vencimiento": (
            lote.fecha_vencimiento.isoformat() if lote.fecha_vencimiento else None
        ),
        "dias_para_vencer": dias,
        "estado_vencimiento": estado,
        "cantidad": format(
            lote.cantidad,
            ".3f",
        ),
        "costo_unitario": format(
            lote.costo_unitario,
            ".4f",
        ),
        "valor": format(valor, ".2f"),
        "activo": lote.activo,
    }


@inventario_bp.get("/lotes")
@login_required
@requerir_permiso("stock.ver")
@requerir_contexto
def listar_lotes():
    if not tiene_capacidad(
        current_user.empresa,
        "control_lotes",
    ):
        return (
            jsonify(
                {
                    "codigo": "capacidad_no_disponible",
                    "mensaje": (
                        "El inventario " "farmacéutico no está " "disponible para esta empresa"
                    ),
                }
            ),
            403,
        )

    try:
        contexto = _contexto_actual()

        consulta = (
            db.select(
                Lote,
                Producto,
            )
            .join(
                Producto,
                db.and_(
                    Producto.id == Lote.producto_id,
                    Producto.empresa_id == Lote.empresa_id,
                ),
            )
            .where(
                Lote.empresa_id == current_user.empresa_id,
                Lote.bodega_id == contexto.bodega.id,
                Producto.eliminado.is_(False),
            )
        )

        producto_id = request.args.get(
            "producto_id",
            type=int,
        )

        if producto_id:
            consulta = consulta.where(Lote.producto_id == producto_id)

        incluir_agotados = request.args.get(
            "incluir_agotados",
            "",
        ).strip().lower() in {"1", "true", "si", "s?"}

        if not incluir_agotados:
            consulta = consulta.where(
                Lote.activo.is_(True),
                Lote.cantidad > 0,
            )

        filas = db.session.execute(
            consulta.order_by(
                Lote.fecha_vencimiento.is_(None),
                Lote.fecha_vencimiento,
                Producto.nombre,
                Lote.numero,
            )
        ).all()

        lotes = [
            _serializar_lote(
                lote,
                producto,
            )
            for lote, producto in filas
        ]

        estado = (request.args.get("estado") or "").strip().lower()

        estados_validos = {
            "",
            "vencido",
            "vence_hoy",
            "proximo_vencer",
            "vigente",
            "sin_vencimiento",
        }

        if estado not in estados_validos:
            return _error(
                ValueError("El estado de vencimiento " "no es válido"),
                "filtro_invalido",
            )

        if estado:
            lotes = [lote for lote in lotes if (lote["estado_vencimiento"] == estado)]

        return jsonify(
            {
                "bodega_id": contexto.bodega.id,
                "bodega_nombre": contexto.bodega.nombre,
                "lotes": lotes,
            }
        )
    except ValueError as exc:
        return _error(
            exc,
            "contexto_invalido",
        )


@inventario_bp.get("/stock")
@login_required
@requerir_permiso("stock.ver")
@requerir_contexto
def listar_stock():
    try:
        contexto = _contexto_actual()

        filas = db.session.execute(
            db.select(
                Inventario,
                Producto,
            )
            .join(
                Producto,
                db.and_(
                    Producto.id == Inventario.producto_id,
                    Producto.empresa_id == Inventario.empresa_id,
                ),
            )
            .where(
                Inventario.empresa_id == current_user.empresa_id,
                Inventario.bodega_id == contexto.bodega.id,
                Producto.eliminado.is_(False),
            )
            .order_by(
                Producto.nombre,
                Producto.codigo,
            )
        ).all()

        return jsonify(
            {
                "bodega_id": contexto.bodega.id,
                "bodega_nombre": contexto.bodega.nombre,
                "stock": [
                    _serializar_stock(
                        inventario,
                        producto,
                        contexto.bodega,
                    )
                    for inventario, producto in filas
                ],
            }
        )
    except ValueError as exc:
        return _error(
            exc,
            "contexto_invalido",
        )


@inventario_bp.get("/movimientos")
@login_required
@requerir_permiso("movimientos.ver")
@requerir_contexto
def listar_movimientos():
    try:
        contexto = _contexto_actual()

        try:
            limite = int(request.args.get("limite", 100))
        except (TypeError, ValueError):
            limite = 100

        limite = min(
            max(limite, 1),
            500,
        )

        filas = db.session.execute(
            db.select(
                Movimiento,
                Producto,
            )
            .join(
                Producto,
                db.and_(
                    Producto.id == Movimiento.producto_id,
                    Producto.empresa_id == Movimiento.empresa_id,
                ),
            )
            .where(
                Movimiento.empresa_id == current_user.empresa_id,
                Movimiento.bodega_id == contexto.bodega.id,
                Producto.eliminado.is_(False),
            )
            .order_by(
                Movimiento.fecha.desc(),
                Movimiento.id.desc(),
            )
            .limit(limite)
        ).all()

        return jsonify(
            {
                "bodega_id": contexto.bodega.id,
                "bodega_nombre": contexto.bodega.nombre,
                "movimientos": [
                    _serializar_movimiento(
                        movimiento,
                        producto,
                    )
                    for movimiento, producto in filas
                ],
            }
        )
    except ValueError as exc:
        return _error(
            exc,
            "contexto_invalido",
        )


@inventario_bp.post("/movimientos")
@login_required
@requerir_permiso("stock.ver")
@requerir_contexto
def registrar_movimiento():
    datos = request.get_json(silent=True) or {}

    tipo = (datos.get("tipo") or "").strip().lower()

    operaciones = {
        "entrada",
        "salida",
        "ajuste",
        "devolucion",
    }

    if tipo not in operaciones:
        return _error(
            ValueError("El tipo de movimiento no es válido"),
            "movimiento_invalido",
        )

    contexto = obtener_contexto(
        current_user,
        crear_automaticamente=False,
    )

    if not contexto:
        return _error(
            ValueError("No existe un contexto operativo válido"),
            "contexto_invalido",
        )

    servicio = ServicioInventario(
        current_user,
        contexto,
    )

    try:
        producto_id = int(datos["producto_id"])
        motivo = datos.get("motivo")

        if tipo == "entrada":
            resultado = servicio.entrada(
                producto_id=producto_id,
                cantidad=datos.get("cantidad"),
                costo_unitario=datos.get("costo_unitario"),
                motivo=motivo,
                numero_lote=datos.get("numero_lote"),
                fecha_vencimiento=datos.get("fecha_vencimiento"),
            )
        elif tipo == "salida":
            resultado = servicio.salida(
                producto_id=producto_id,
                cantidad=datos.get("cantidad"),
                precio_unitario=datos.get("precio_unitario"),
                motivo=motivo,
            )
        elif tipo == "devolucion":
            resultado = servicio.devolucion(
                producto_id=producto_id,
                cantidad=datos.get("cantidad"),
                costo_unitario=datos.get("costo_unitario"),
                motivo=motivo,
                numero_lote=datos.get("numero_lote"),
                fecha_vencimiento=datos.get("fecha_vencimiento"),
            )
        else:
            resultado = servicio.ajuste(
                producto_id=producto_id,
                stock_final=datos.get("stock_final"),
                motivo=motivo,
            )

        return (
            jsonify(
                _serializar_resultado(
                    resultado,
                    tipo,
                )
            ),
            201,
        )
    except ErrorInventario as exc:
        return _error(exc)
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        return _error(
            exc,
            "movimiento_invalido",
        )
