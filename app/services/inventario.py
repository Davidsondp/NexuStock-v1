"""Única puerta de escritura del inventario de NexuStock."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError

from ..models import (
    Bodega,
    Inventario,
    Lote,
    Movimiento,
    MovimientoLote,
    Producto,
    db,
    utcnow,
)
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from .contexto import ContextoOperacion
from .perfiles_empresa import tiene_capacidad

TRES_DECIMALES = Decimal("0.001")
CUATRO_DECIMALES = Decimal("0.0001")


class ErrorInventario(ValueError):
    codigo = "error_inventario"


class StockInsuficiente(ErrorInventario):
    codigo = "stock_insuficiente"


class LimiteMovimientosAlcanzado(ErrorInventario):
    codigo = "limite_movimientos"


@dataclass(frozen=True)
class ResultadoMovimiento:
    inventario_id: int
    movimiento_id: int
    stock_anterior: Decimal
    stock_nuevo: Decimal
    costo_promedio: Decimal


def _decimal(valor, nombre: str, decimales: Decimal) -> Decimal:
    try:
        resultado = Decimal(str(valor)).quantize(decimales, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ErrorInventario(f"{nombre} no es válido") from exc
    return resultado


def _inicio_mes(ahora: datetime) -> datetime:
    return ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _cantidad_positiva(valor) -> Decimal:
    cantidad = _decimal(valor, "Cantidad", TRES_DECIMALES)
    if cantidad <= 0:
        raise ErrorInventario("La cantidad debe ser mayor que cero")
    return cantidad


def _fecha_lote(valor, nombre: str):
    if valor is None or valor == "":
        return None

    if isinstance(valor, datetime):
        return valor.date()

    if isinstance(valor, date):
        return valor

    try:
        return date.fromisoformat(str(valor).strip())
    except (TypeError, ValueError) as exc:
        raise ErrorInventario(f"{nombre} no es valido") from exc


class ServicioInventario:
    """Ejecuta saldo, movimiento y auditoría en una misma transacción."""

    def __init__(self, usuario, contexto: ContextoOperacion):
        self.usuario = usuario
        self.contexto = contexto
        if usuario.empresa_id != contexto.empresa_id:
            raise PermissionError("El contexto no pertenece al usuario")

    def entrada(
        self,
        *,
        producto_id: int,
        cantidad,
        costo_unitario,
        motivo: str,
        referencia_tipo=None,
        referencia_id=None,
        numero_lote=None,
        fecha_vencimiento=None,
        confirmar: bool = True,
    ) -> ResultadoMovimiento:
        return self._ejecutar(
            "entrada",
            "stock.entrada",
            producto_id,
            _cantidad_positiva(cantidad),
            costo_unitario=costo_unitario,
            motivo=motivo,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            numero_lote=numero_lote,
            fecha_vencimiento=fecha_vencimiento,
            confirmar=confirmar,
        )

    def salida(
        self,
        *,
        producto_id: int,
        cantidad,
        motivo: str,
        precio_unitario=None,
        referencia_tipo=None,
        referencia_id=None,
        confirmar: bool = True,
    ) -> ResultadoMovimiento:
        return self._ejecutar(
            "salida",
            "stock.salida",
            producto_id,
            -_cantidad_positiva(cantidad),
            precio_unitario=precio_unitario,
            motivo=motivo,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            confirmar=confirmar,
        )

    def devolucion(
        self,
        *,
        producto_id: int,
        cantidad,
        motivo: str,
        costo_unitario=None,
        referencia_tipo=None,
        referencia_id=None,
        numero_lote=None,
        fecha_vencimiento=None,
        confirmar: bool = True,
    ) -> ResultadoMovimiento:
        return self._ejecutar(
            "devolucion",
            "stock.devolucion",
            producto_id,
            _cantidad_positiva(cantidad),
            costo_unitario=costo_unitario,
            motivo=motivo,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            numero_lote=numero_lote,
            fecha_vencimiento=fecha_vencimiento,
            confirmar=confirmar,
        )

    def transferencia_salida(
        self, *, producto_id: int, cantidad, motivo: str, referencia_id: int, confirmar: bool = True
    ) -> ResultadoMovimiento:
        return self._ejecutar(
            "transferencia",
            "stock.transferencia",
            producto_id,
            -_cantidad_positiva(cantidad),
            motivo=motivo,
            referencia_tipo="transferencia",
            referencia_id=referencia_id,
            confirmar=confirmar,
        )

    def transferencia_entrada(
        self,
        *,
        producto_id: int,
        cantidad,
        costo_unitario,
        motivo: str,
        referencia_id: int,
        confirmar: bool = True,
    ) -> ResultadoMovimiento:
        return self._ejecutar(
            "transferencia",
            "stock.transferencia",
            producto_id,
            _cantidad_positiva(cantidad),
            costo_unitario=costo_unitario,
            motivo=motivo,
            referencia_tipo="transferencia",
            referencia_id=referencia_id,
            confirmar=confirmar,
        )

    def ajuste(
        self, *, producto_id: int, stock_final, motivo: str, confirmar: bool = True
    ) -> ResultadoMovimiento:
        try:
            producto, inventario = self._obtener_entidades(producto_id)

            if producto.controla_lotes or producto.controla_vencimiento:
                raise ErrorInventario("Los productos controlados " "deben ajustarse por lote")

            objetivo = _decimal(
                stock_final,
                "Stock final",
                TRES_DECIMALES,
            )

            if objetivo < 0:
                raise ErrorInventario("El stock final no puede ser negativo")

            delta = objetivo - Decimal(inventario.cantidad)

            return self._ejecutar(
                "ajuste",
                "stock.ajuste",
                producto.id,
                delta,
                motivo=motivo,
                inventario_bloqueado=inventario,
                confirmar=confirmar,
            )
        except Exception:
            db.session.rollback()
            raise

    def _ejecutar(
        self,
        tipo: str,
        permiso: str,
        producto_id: int,
        cantidad,
        *,
        motivo: str,
        costo_unitario=None,
        precio_unitario=None,
        referencia_tipo=None,
        referencia_id=None,
        inventario_bloqueado=None,
        numero_lote=None,
        fecha_vencimiento=None,
        confirmar: bool = True,
    ) -> ResultadoMovimiento:
        try:
            decision = evaluar_permiso(self.usuario, permiso, empresa_id=self.contexto.empresa_id)
            if not decision.permitido:
                raise PermissionError(decision.mensaje)
            cantidad = _decimal(cantidad, "Cantidad", TRES_DECIMALES)
            if cantidad == 0:
                raise ErrorInventario("La cantidad del movimiento no puede ser cero")
            if not (motivo or "").strip():
                raise ErrorInventario("El motivo es obligatorio")
            self._validar_limite_mensual()
            producto, inventario = self._obtener_entidades(producto_id, inventario_bloqueado)
            anterior = Decimal(inventario.cantidad)
            nuevo = anterior + cantidad
            if nuevo < Decimal(inventario.cantidad_reservada):
                raise StockInsuficiente("Stock disponible insuficiente")

            asignaciones_lote = []

            if cantidad < 0 and (producto.controla_lotes or producto.controla_vencimiento):
                asignaciones_lote = self._preparar_salida_lotes(
                    producto,
                    -cantidad,
                )

            costo_anterior = Decimal(inventario.costo_promedio)
            costo = (
                _decimal(costo_unitario, "Costo unitario", CUATRO_DECIMALES)
                if costo_unitario is not None
                else costo_anterior
            )
            if costo < 0:
                raise ErrorInventario("El costo unitario no puede ser negativo")

            entrada_lote = None

            if cantidad > 0:
                entrada_lote = self._preparar_entrada_lote(
                    producto,
                    cantidad,
                    costo,
                    numero_lote,
                    fecha_vencimiento,
                )

            if cantidad > 0 and nuevo > 0:
                costo_nuevo = ((anterior * costo_anterior) + (cantidad * costo)) / nuevo
                inventario.costo_promedio = costo_nuevo.quantize(
                    CUATRO_DECIMALES, rounding=ROUND_HALF_UP
                )
            inventario.cantidad = nuevo

            precio = (
                _decimal(precio_unitario, "Precio unitario", Decimal("0.01"))
                if precio_unitario is not None
                else None
            )
            if precio is not None and precio < 0:
                raise ErrorInventario("El precio unitario no puede ser negativo")
            movimiento = Movimiento(
                empresa_id=self.contexto.empresa_id,
                producto_id=producto.id,
                bodega_id=self.contexto.bodega.id,
                usuario_id=self.usuario.id,
                tipo=tipo,
                cantidad=cantidad,
                stock_anterior=anterior,
                stock_nuevo=nuevo,
                costo_unitario=costo,
                precio_unitario=precio,
                referencia_tipo=referencia_tipo,
                referencia_id=referencia_id,
                motivo=motivo.strip(),
            )
            db.session.add(movimiento)
            db.session.flush()

            if entrada_lote:
                self._registrar_entrada_lote(
                    movimiento,
                    entrada_lote,
                )

            if asignaciones_lote:
                self._registrar_salida_lotes(
                    movimiento,
                    asignaciones_lote,
                )

            registrar_auditoria(
                accion=f"inventario.{tipo}",
                modulo="inventario",
                usuario_id=self.usuario.id,
                empresa_id=self.contexto.empresa_id,
                entidad_tipo="Movimiento",
                entidad_id=movimiento.id,
                datos_anteriores={"cantidad": str(anterior)},
                datos_nuevos={
                    "cantidad": str(nuevo),
                    "producto_id": producto.id,
                    "bodega_id": self.contexto.bodega.id,
                },
            )
            if confirmar:
                db.session.commit()
            else:
                db.session.flush()
            return ResultadoMovimiento(
                inventario.id, movimiento.id, anterior, nuevo, Decimal(inventario.costo_promedio)
            )
        except Exception:
            db.session.rollback()
            raise

    def _preparar_entrada_lote(
        self,
        producto,
        cantidad: Decimal,
        costo: Decimal,
        numero_lote,
        fecha_vencimiento,
    ):
        numero = str(numero_lote).strip() if numero_lote is not None else ""

        informa_vencimiento = fecha_vencimiento not in (None, "")
        solicita_trazabilidad = bool(numero or informa_vencimiento)

        if solicita_trazabilidad and not tiene_capacidad(
            self.usuario.empresa,
            "control_lotes",
        ):
            raise ErrorInventario("El control de lotes no está " "disponible para esta empresa")

        if informa_vencimiento and not tiene_capacidad(
            self.usuario.empresa,
            "control_vencimientos",
        ):
            raise ErrorInventario(
                "El control de vencimientos " "no está disponible para " "esta empresa"
            )

        controla = producto.controla_lotes or producto.controla_vencimiento

        if solicita_trazabilidad and not controla:
            raise ErrorInventario("Este producto no utiliza " "control por lotes")

        if controla and not numero:
            raise ErrorInventario("El número de lote es obligatorio")

        if not controla and not numero:
            return None

        vencimiento = _fecha_lote(
            fecha_vencimiento,
            "Fecha de vencimiento",
        )

        if producto.controla_vencimiento and vencimiento is None:
            raise ErrorInventario("La fecha de vencimiento " "es obligatoria")

        if vencimiento is not None and vencimiento < date.today():
            raise ErrorInventario("No se puede ingresar " "un lote vencido")

        lote = db.session.scalar(
            db.select(Lote)
            .where(
                Lote.empresa_id == self.contexto.empresa_id,
                Lote.producto_id == producto.id,
                Lote.bodega_id == self.contexto.bodega.id,
                Lote.numero == numero,
            )
            .with_for_update()
        )

        if lote:
            if not lote.activo:
                raise ErrorInventario("El lote se encuentra inactivo")

            if lote.fecha_vencimiento and vencimiento and lote.fecha_vencimiento != vencimiento:
                raise ErrorInventario("El lote ya existe con otra " "fecha de vencimiento")

            saldo_anterior = Decimal(lote.cantidad)
            saldo_nuevo = (saldo_anterior + cantidad).quantize(TRES_DECIMALES)

            if saldo_nuevo <= 0:
                raise ErrorInventario("El saldo del lote " "debe ser positivo")

            costo_anterior = Decimal(lote.costo_unitario)
            costo_nuevo = ((saldo_anterior * costo_anterior) + (cantidad * costo)) / saldo_nuevo

            lote.cantidad = saldo_nuevo
            lote.costo_unitario = costo_nuevo.quantize(
                CUATRO_DECIMALES,
                rounding=ROUND_HALF_UP,
            )
            lote.fecha_vencimiento = lote.fecha_vencimiento or vencimiento
        else:
            saldo_anterior = Decimal("0.000")
            saldo_nuevo = Decimal(cantidad).quantize(TRES_DECIMALES)

            lote = Lote(
                empresa_id=self.contexto.empresa_id,
                producto_id=producto.id,
                bodega_id=self.contexto.bodega.id,
                numero=numero,
                fecha_vencimiento=vencimiento,
                cantidad=saldo_nuevo,
                costo_unitario=costo,
                activo=True,
            )
            db.session.add(lote)
            db.session.flush()

        return (
            lote,
            Decimal(cantidad).quantize(TRES_DECIMALES),
            saldo_anterior,
            saldo_nuevo,
        )

    def _registrar_entrada_lote(
        self,
        movimiento,
        entrada_lote,
    ) -> None:
        (
            lote,
            cantidad,
            saldo_anterior,
            saldo_nuevo,
        ) = entrada_lote

        db.session.add(
            MovimientoLote(
                empresa_id=self.contexto.empresa_id,
                movimiento_id=movimiento.id,
                lote_id=lote.id,
                producto_id=movimiento.producto_id,
                bodega_id=movimiento.bodega_id,
                usuario_id=self.usuario.id,
                cantidad=cantidad,
                saldo_anterior=saldo_anterior,
                saldo_nuevo=saldo_nuevo,
                fecha=movimiento.fecha,
            )
        )

    def _preparar_salida_lotes(
        self,
        producto,
        cantidad: Decimal,
    ):
        consulta = db.select(Lote).where(
            Lote.empresa_id == self.contexto.empresa_id,
            Lote.producto_id == producto.id,
            Lote.bodega_id == self.contexto.bodega.id,
            Lote.activo.is_(True),
            Lote.cantidad > 0,
        )

        if producto.controla_vencimiento:
            consulta = consulta.where(
                Lote.fecha_vencimiento.is_not(None),
                Lote.fecha_vencimiento >= date.today(),
            )

        consulta = consulta.order_by(
            db.case(
                (
                    Lote.fecha_vencimiento.is_(None),
                    1,
                ),
                else_=0,
            ),
            Lote.fecha_vencimiento.asc(),
            Lote.creado_en.asc(),
            Lote.id.asc(),
        ).with_for_update()

        lotes = list(db.session.scalars(consulta))

        restante = Decimal(cantidad)
        asignaciones = []

        for lote in lotes:
            if restante <= 0:
                break

            disponible = Decimal(lote.cantidad)
            retiro = min(
                disponible,
                restante,
            ).quantize(TRES_DECIMALES)

            if retiro <= 0:
                continue

            asignaciones.append((lote, retiro))
            restante -= retiro

        if restante > 0:
            raise StockInsuficiente("Stock disponible por lote " "insuficiente")

        return asignaciones

    def _registrar_salida_lotes(
        self,
        movimiento,
        asignaciones,
    ) -> None:
        for lote, retiro in asignaciones:
            saldo_anterior = Decimal(lote.cantidad)
            cantidad = -Decimal(retiro).quantize(TRES_DECIMALES)
            saldo_nuevo = (saldo_anterior + cantidad).quantize(TRES_DECIMALES)

            if saldo_nuevo < 0:
                raise StockInsuficiente("Stock disponible por lote " "insuficiente")

            lote.cantidad = saldo_nuevo

            db.session.add(
                MovimientoLote(
                    empresa_id=self.contexto.empresa_id,
                    movimiento_id=movimiento.id,
                    lote_id=lote.id,
                    producto_id=movimiento.producto_id,
                    bodega_id=movimiento.bodega_id,
                    usuario_id=self.usuario.id,
                    cantidad=cantidad,
                    saldo_anterior=saldo_anterior,
                    saldo_nuevo=saldo_nuevo,
                    fecha=movimiento.fecha,
                )
            )

    def _obtener_entidades(self, producto_id: int, inventario_existente=None):
        producto = db.session.scalar(
            db.select(Producto).where(
                Producto.id == producto_id,
                Producto.empresa_id == self.contexto.empresa_id,
                Producto.activo.is_(True),
                Producto.eliminado.is_(False),
            )
        )
        bodega = db.session.scalar(
            db.select(Bodega).where(
                Bodega.id == self.contexto.bodega.id,
                Bodega.empresa_id == self.contexto.empresa_id,
                Bodega.activa.is_(True),
                Bodega.eliminado.is_(False),
            )
        )
        if not producto or not bodega:
            raise PermissionError("Producto o bodega fuera del ámbito autorizado")
        inventario = inventario_existente or db.session.scalar(
            db.select(Inventario)
            .where(
                Inventario.empresa_id == self.contexto.empresa_id,
                Inventario.bodega_id == bodega.id,
                Inventario.producto_id == producto.id,
            )
            .with_for_update()
        )
        if inventario is None:
            inventario = Inventario(
                empresa_id=self.contexto.empresa_id,
                bodega_id=bodega.id,
                producto_id=producto.id,
                cantidad=0,
                cantidad_reservada=0,
                costo_promedio=0,
            )
            db.session.add(inventario)
            try:
                db.session.flush()
            except IntegrityError:
                # Una creación concurrente gana; reiniciamos para cargar y bloquear esa fila.
                db.session.rollback()
                raise ErrorInventario("Conflicto concurrente al crear el inventario; reintenta")
        return producto, inventario

    def _validar_limite_mensual(self) -> None:
        suscripcion = self.usuario.empresa.suscripcion_actual
        limite = suscripcion.plan.limite_movimientos_mes
        if limite is None:
            return
        ahora = utcnow()
        cantidad = db.session.scalar(
            db.select(db.func.count(Movimiento.id)).where(
                Movimiento.empresa_id == self.contexto.empresa_id,
                Movimiento.fecha >= _inicio_mes(ahora),
                Movimiento.fecha <= ahora,
            )
        )
        if cantidad >= limite:
            raise LimiteMovimientosAlcanzado("Se alcanzó el límite mensual de movimientos del plan")
