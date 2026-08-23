"""Definiciones reutilizables de reportes y snapshots diarios."""

from sqlalchemy.exc import IntegrityError

from ..models import Inventario, ReportePersonalizado, SnapshotInventario, db, utcnow
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from .reportes import ServicioReportes, construir_periodo

TIPOS = frozenset({"productos", "stock", "movimientos", "analitica"})


class ErrorReportePersonalizado(ValueError):
    codigo = "reporte_personalizado_invalido"


class ServicioReportesPersonalizados:
    def __init__(self, actor):
        self.actor = actor
        if not actor.empresa_id or actor.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def listar(self):
        self._exigir("reportes.personalizados")
        return list(
            db.session.scalars(
                db.select(ReportePersonalizado)
                .where(
                    ReportePersonalizado.empresa_id == self.actor.empresa_id,
                    ReportePersonalizado.activo.is_(True),
                    ReportePersonalizado.eliminado.is_(False),
                )
                .order_by(ReportePersonalizado.nombre)
            )
        )

    def crear(self, *, nombre, tipo, configuracion=None):
        self._exigir("reportes.personalizados")
        nombre = (nombre or "").strip()
        if not nombre or tipo not in TIPOS:
            raise ErrorReportePersonalizado("Nombre y tipo válido son obligatorios")
        configuracion = configuracion or {}
        if not isinstance(configuracion, dict):
            raise ErrorReportePersonalizado("La configuración debe ser un objeto")
        permitidos = {"bodega_id", "limite", "dias"}
        if set(configuracion) - permitidos:
            raise ErrorReportePersonalizado("La configuración contiene opciones no admitidas")
        try:
            reporte = ReportePersonalizado(
                empresa_id=self.actor.empresa_id,
                creado_por_id=self.actor.id,
                nombre=nombre,
                tipo=tipo,
                configuracion=configuracion,
            )
            db.session.add(reporte)
            db.session.flush()
            self._auditar(reporte, "creado")
            db.session.commit()
            return reporte
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorReportePersonalizado("Ya existe un reporte con ese nombre") from exc

    def ejecutar(self, reporte_id, *, desde=None, hasta=None):
        self._exigir("reportes.personalizados")
        reporte = self._obtener(reporte_id)
        periodo = construir_periodo(desde, hasta)
        configuracion = reporte.configuracion or {}
        servicio = ServicioReportes(self.actor)
        if reporte.tipo == "productos":
            return [{"codigo": p.codigo, "nombre": p.nombre} for p in servicio.productos()]
        if reporte.tipo == "stock":
            return [
                {
                    "producto": p.nombre,
                    "bodega": b.nombre,
                    "cantidad": str(i.cantidad),
                    "disponible": str(i.cantidad_disponible),
                }
                for i, p, b in servicio.stock(bodega_id=configuracion.get("bodega_id"))
            ]
        if reporte.tipo == "movimientos":
            return [
                {"fecha": m.fecha.isoformat(), "tipo": m.tipo, "cantidad": str(m.cantidad)}
                for m in servicio.movimientos(
                    periodo,
                    bodega_id=configuracion.get("bodega_id"),
                    limite=configuracion.get("limite", 500),
                )
            ]
        return servicio.analitica(
            periodo,
            bodega_id=configuracion.get("bodega_id"),
            limite=configuracion.get("limite", 10),
        )

    def eliminar(self, reporte_id):
        self._exigir("reportes.personalizados")
        reporte = self._obtener(reporte_id)
        reporte.activo = False
        reporte.soft_delete()
        self._auditar(reporte, "eliminado")
        db.session.commit()

    def _obtener(self, reporte_id):
        reporte = db.session.scalar(
            db.select(ReportePersonalizado).where(
                ReportePersonalizado.id == reporte_id,
                ReportePersonalizado.empresa_id == self.actor.empresa_id,
                ReportePersonalizado.eliminado.is_(False),
            )
        )
        if not reporte:
            raise PermissionError("Reporte no autorizado")
        return reporte

    def _auditar(self, reporte, accion):
        registrar_auditoria(
            accion=f"reporte_personalizado.{accion}",
            modulo="reportes",
            usuario_id=self.actor.id,
            empresa_id=self.actor.empresa_id,
            entidad_tipo="ReportePersonalizado",
            entidad_id=reporte.id,
            datos_nuevos={"nombre": reporte.nombre, "tipo": reporte.tipo},
        )

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.actor, permiso, empresa_id=self.actor.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)


def capturar_snapshot_inventario(fecha=None):
    fecha = fecha or utcnow().date()
    inventarios = list(db.session.scalars(db.select(Inventario)))
    creados = 0
    for inventario in inventarios:
        existente = db.session.scalar(
            db.select(SnapshotInventario.id).where(
                SnapshotInventario.empresa_id == inventario.empresa_id,
                SnapshotInventario.producto_id == inventario.producto_id,
                SnapshotInventario.bodega_id == inventario.bodega_id,
                SnapshotInventario.fecha == fecha,
            )
        )
        if existente:
            continue
        db.session.add(
            SnapshotInventario(
                empresa_id=inventario.empresa_id,
                producto_id=inventario.producto_id,
                bodega_id=inventario.bodega_id,
                fecha=fecha,
                cantidad=inventario.cantidad,
                cantidad_reservada=inventario.cantidad_reservada,
                costo_promedio=inventario.costo_promedio,
            )
        )
        creados += 1
    db.session.commit()
    return creados
