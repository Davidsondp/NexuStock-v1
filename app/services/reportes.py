"""Reportes y analítica calculados desde fuentes transaccionales reales."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from ..models import (
    Bodega,
    ConfiguracionEmpresa,
    Inventario,
    Movimiento,
    Producto,
    SnapshotInventario,
    Venta,
    VentaItem,
    db,
    utcnow,
)
from ..permisos import evaluar_permiso
from .contexto import sucursales_autorizadas

DOS = Decimal("0.01")
CUATRO = Decimal("0.0001")


class ErrorReporte(ValueError):
    codigo = "reporte_invalido"


@dataclass(frozen=True)
class Periodo:
    desde: datetime
    hasta: datetime


def construir_periodo(desde=None, hasta=None, *, dias_predeterminados=30) -> Periodo:
    hoy = utcnow().date()
    try:
        fecha_desde = (
            date.fromisoformat(desde) if desde else hoy - timedelta(days=dias_predeterminados - 1)
        )
        fecha_hasta = date.fromisoformat(hasta) if hasta else hoy
    except (TypeError, ValueError) as exc:
        raise ErrorReporte("Las fechas deben tener formato AAAA-MM-DD") from exc
    if fecha_desde > fecha_hasta:
        raise ErrorReporte("La fecha inicial no puede ser posterior a la final")
    if (fecha_hasta - fecha_desde).days > 366:
        raise ErrorReporte("El período no puede superar 366 días")
    return Periodo(datetime.combine(fecha_desde, time.min), datetime.combine(fecha_hasta, time.max))


class ServicioReportes:
    def __init__(self, usuario):
        self.usuario = usuario
        if not usuario.empresa_id or usuario.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def productos(self):
        self._exigir("reportes.ver")
        return list(
            db.session.scalars(
                db.select(Producto)
                .where(
                    Producto.empresa_id == self.usuario.empresa_id,
                    Producto.activo.is_(True),
                    Producto.eliminado.is_(False),
                )
                .order_by(Producto.nombre)
            )
        )

    def stock(self, *, bodega_id=None):
        self._exigir("reportes.ver")
        bodegas = self._bodegas(bodega_id)
        return list(
            db.session.execute(
                db.select(Inventario, Producto, Bodega)
                .join(
                    Producto,
                    db.and_(
                        Producto.id == Inventario.producto_id,
                        Producto.empresa_id == Inventario.empresa_id,
                    ),
                )
                .join(
                    Bodega,
                    db.and_(
                        Bodega.id == Inventario.bodega_id,
                        Bodega.empresa_id == Inventario.empresa_id,
                    ),
                )
                .where(
                    Inventario.empresa_id == self.usuario.empresa_id,
                    Inventario.bodega_id.in_(bodegas),
                    Producto.eliminado.is_(False),
                )
                .order_by(Producto.nombre, Bodega.nombre)
            )
        )

    def dinero_dormido(self, *, bodega_id=None):
        """Calcula capital inmovilizado sin duplicar sobrestock y baja rotación."""
        self._exigir("dashboard.ver")
        bodegas = self._bodegas(bodega_id)
        configuracion = db.session.scalar(
            db.select(ConfiguracionEmpresa).where(
                ConfiguracionEmpresa.empresa_id == self.usuario.empresa_id
            )
        )
        dias = configuracion.dias_sin_movimiento if configuracion else 90
        corte = utcnow() - timedelta(days=dias)
        ultimos = {
            (producto_id, bodega): fecha
            for producto_id, bodega, fecha in db.session.execute(
                db.select(
                    Movimiento.producto_id,
                    Movimiento.bodega_id,
                    db.func.max(Movimiento.fecha),
                )
                .where(
                    Movimiento.empresa_id == self.usuario.empresa_id,
                    Movimiento.bodega_id.in_(bodegas),
                )
                .group_by(Movimiento.producto_id, Movimiento.bodega_id)
            )
        }
        filas = []
        total = Decimal(0)
        unidades_total = Decimal(0)
        for inventario, producto, bodega in self.stock(bodega_id=bodega_id):
            disponible = max(
                Decimal(inventario.cantidad) - Decimal(inventario.cantidad_reservada),
                Decimal(0),
            )
            exceso = Decimal(0)
            if producto.stock_maximo is not None:
                exceso = max(
                    Decimal(inventario.cantidad) - Decimal(producto.stock_maximo),
                    Decimal(0),
                )
                exceso = min(exceso, disponible)
            ultimo = ultimos.get((producto.id, bodega.id))
            sin_movimiento = disponible > 0 and (ultimo is None or ultimo < corte)
            unidades = max(exceso, disponible if sin_movimiento else Decimal(0))
            if unidades <= 0:
                continue
            monto = unidades * Decimal(inventario.costo_promedio)
            total += monto
            unidades_total += unidades
            causas = []
            if exceso > 0:
                causas.append("sobrestock")
            if sin_movimiento:
                causas.append("sin_movimiento")
            filas.append(
                {
                    "producto_id": producto.id,
                    "producto": producto.nombre,
                    "bodega_id": bodega.id,
                    "bodega": bodega.nombre,
                    "unidades": str(unidades),
                    "monto": str(monto.quantize(DOS)),
                    "causas": causas,
                    "ultimo_movimiento": ultimo.isoformat() if ultimo else None,
                }
            )
        filas.sort(key=lambda fila: Decimal(fila["monto"]), reverse=True)
        return {
            "monto": str(total.quantize(DOS)),
            "unidades": str(unidades_total),
            "productos": len(filas),
            "dias_sin_movimiento": dias,
            "detalle": filas[:5],
            "criterio": (
                "Stock disponible sobre el máximo o sin movimientos; "
                "cada unidad se contabiliza una sola vez."
            ),
        }

    def movimientos(self, periodo: Periodo, *, bodega_id=None, limite=500):
        self._exigir("reportes.ver")
        bodegas = self._bodegas(bodega_id)
        limite = min(max(int(limite), 1), 2000)
        return list(
            db.session.scalars(
                db.select(Movimiento)
                .where(
                    Movimiento.empresa_id == self.usuario.empresa_id,
                    Movimiento.bodega_id.in_(bodegas),
                    Movimiento.fecha >= periodo.desde,
                    Movimiento.fecha <= periodo.hasta,
                )
                .order_by(Movimiento.fecha.desc())
                .limit(limite)
            )
        )

    def analitica(self, periodo: Periodo, *, bodega_id=None, limite=10):
        self._exigir("analitica.ver")
        bodegas = self._bodegas(bodega_id)
        limite = min(max(int(limite), 1), 100)
        inventarios = list(
            db.session.execute(
                db.select(Inventario, Producto)
                .join(
                    Producto,
                    db.and_(
                        Producto.id == Inventario.producto_id,
                        Producto.empresa_id == Inventario.empresa_id,
                    ),
                )
                .where(
                    Inventario.empresa_id == self.usuario.empresa_id,
                    Inventario.bodega_id.in_(bodegas),
                    Producto.eliminado.is_(False),
                )
            )
        )
        ventas = list(
            db.session.scalars(
                db.select(Venta).where(
                    Venta.empresa_id == self.usuario.empresa_id,
                    Venta.bodega_id.in_(bodegas),
                    Venta.estado == "confirmada",
                    Venta.confirmada_en >= periodo.desde,
                    Venta.confirmada_en <= periodo.hasta,
                )
            )
        )
        ids_ventas = [v.id for v in ventas]
        items = (
            list(
                db.session.scalars(
                    db.select(VentaItem).where(
                        VentaItem.empresa_id == self.usuario.empresa_id,
                        VentaItem.venta_id.in_(ids_ventas),
                    )
                )
            )
            if ids_ventas
            else []
        )
        movimientos = (
            list(
                db.session.scalars(
                    db.select(Movimiento).where(
                        Movimiento.empresa_id == self.usuario.empresa_id,
                        Movimiento.bodega_id.in_(bodegas),
                        Movimiento.referencia_tipo == "venta",
                        Movimiento.referencia_id.in_(ids_ventas),
                    )
                )
            )
            if ids_ventas
            else []
        )
        costo_por_venta_producto = {
            (m.referencia_id, m.producto_id): Decimal(m.costo_unitario or 0) for m in movimientos
        }
        venta_por_id = {v.id: v for v in ventas}
        agrupados = {}
        costo_ventas = Decimal(0)
        for item in items:
            cantidad = Decimal(item.cantidad)
            costo = costo_por_venta_producto.get((item.venta_id, item.producto_id), Decimal(0))
            costo_ventas += cantidad * costo
            fila = agrupados.setdefault(
                item.producto_id,
                {"unidades": Decimal(0), "ingresos": Decimal(0), "costo": Decimal(0)},
            )
            fila["unidades"] += cantidad
            fila["ingresos"] += Decimal(item.total)
            fila["costo"] += cantidad * costo
        nombres = {p.id: p.nombre for _, p in inventarios}
        mas_vendidos = [
            {
                "producto_id": pid,
                "producto": nombres.get(pid, "Producto"),
                "unidades": str(d["unidades"]),
                "ingresos": str(d["ingresos"].quantize(DOS)),
                "margen_bruto": str((d["ingresos"] - d["costo"]).quantize(DOS)),
            }
            for pid, d in sorted(agrupados.items(), key=lambda x: x[1]["unidades"], reverse=True)[
                :limite
            ]
        ]
        valor = sum(
            (Decimal(i.cantidad) * Decimal(i.costo_promedio) for i, _ in inventarios), Decimal(0)
        )
        ingresos = sum((Decimal(v.total) for v in ventas), Decimal(0))
        unidades = sum((d["unidades"] for d in agrupados.values()), Decimal(0))
        stock_actual = sum((Decimal(i.cantidad) for i, _ in inventarios), Decimal(0))
        cortes = db.session.execute(
            db.select(
                SnapshotInventario.fecha,
                db.func.sum(SnapshotInventario.cantidad),
            )
            .where(
                SnapshotInventario.empresa_id == self.usuario.empresa_id,
                SnapshotInventario.bodega_id.in_(bodegas),
                SnapshotInventario.fecha >= periodo.desde.date(),
                SnapshotInventario.fecha <= periodo.hasta.date(),
            )
            .group_by(SnapshotInventario.fecha)
        ).all()
        inventario_promedio = (
            sum((Decimal(total) for _, total in cortes), Decimal(0)) / Decimal(len(cortes))
            if cortes
            else stock_actual
        )
        dias = Decimal((periodo.hasta.date() - periodo.desde.date()).days + 1)
        consumo_diario = unidades / dias if dias else Decimal(0)
        cobertura = stock_actual / consumo_diario if consumo_diario > 0 else None
        sin_movimiento, sobrestock = [], []
        for inventario, producto in inventarios:
            ultimo = db.session.scalar(
                db.select(db.func.max(Movimiento.fecha)).where(
                    Movimiento.empresa_id == self.usuario.empresa_id,
                    Movimiento.bodega_id == inventario.bodega_id,
                    Movimiento.producto_id == producto.id,
                )
            )
            if ultimo is None or ultimo < periodo.desde:
                sin_movimiento.append(
                    {
                        "producto_id": producto.id,
                        "producto": producto.nombre,
                        "bodega_id": inventario.bodega_id,
                        "stock": str(inventario.cantidad),
                        "ultimo_movimiento": ultimo.isoformat() if ultimo else None,
                    }
                )
            if producto.stock_maximo is not None and Decimal(inventario.cantidad) > Decimal(
                producto.stock_maximo
            ):
                sobrestock.append(
                    {
                        "producto_id": producto.id,
                        "producto": producto.nombre,
                        "bodega_id": inventario.bodega_id,
                        "exceso": str(
                            Decimal(inventario.cantidad) - Decimal(producto.stock_maximo)
                        ),
                    }
                )
        return {
            "periodo": {
                "desde": periodo.desde.date().isoformat(),
                "hasta": periodo.hasta.date().isoformat(),
            },
            "ventas_confirmadas": len(ventas),
            "ingresos": str(ingresos.quantize(DOS)),
            "costo_ventas": str(costo_ventas.quantize(DOS)),
            "margen_bruto": str((ingresos - costo_ventas).quantize(DOS)),
            "valor_inventario_actual": str(valor.quantize(DOS)),
            "unidades_vendidas": str(unidades),
            "dias_cobertura_actual": (
                str(cobertura.quantize(DOS)) if cobertura is not None else None
            ),
            "inventario_promedio": str(inventario_promedio.quantize(DOS)),
            "dias_con_snapshot": len(cortes),
            "rotacion_inventario": (
                str((unidades / inventario_promedio).quantize(CUATRO))
                if inventario_promedio
                else None
            ),
            "nota_rotacion": (
                "Calculada con inventario promedio de snapshots diarios."
                if cortes
                else "Sin snapshots en el periodo; se usa temporalmente el stock actual."
            ),
            "productos_mas_vendidos": mas_vendidos,
            "productos_sin_movimiento": sin_movimiento,
            "sobrestock": sobrestock,
        }

    def resumen_ejecutivo(self, periodo: Periodo, *, bodega_id=None):
        self._exigir("dashboard.ejecutivo")
        datos = self.analitica(periodo, bodega_id=bodega_id, limite=5)
        ingresos = Decimal(datos["ingresos"])
        margen = Decimal(datos["margen_bruto"])
        cantidad_ventas = datos["ventas_confirmadas"]
        datos["ticket_promedio"] = str(
            (ingresos / cantidad_ventas).quantize(DOS)
            if cantidad_ventas
            else Decimal(0).quantize(DOS)
        )
        datos["margen_bruto_porcentaje"] = str(
            ((margen / ingresos) * 100).quantize(DOS) if ingresos else Decimal(0).quantize(DOS)
        )
        datos["alcance"] = (
            "Indicadores operacionales calculados desde ventas confirmadas e inventario actual."
        )
        return datos

    def _bodegas(self, bodega_id=None):
        sucursales = {s.id for s in sucursales_autorizadas(self.usuario)}
        ids = set(
            db.session.scalars(
                db.select(Bodega.id).where(
                    Bodega.empresa_id == self.usuario.empresa_id,
                    Bodega.sucursal_id.in_(sucursales),
                    Bodega.activa.is_(True),
                    Bodega.eliminado.is_(False),
                )
            )
        )
        if bodega_id is not None:
            if bodega_id not in ids:
                raise PermissionError("Bodega no autorizada")
            return {bodega_id}
        return ids

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.usuario, permiso, empresa_id=self.usuario.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)
