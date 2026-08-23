"""Consulta y ciclo de vida de números de serie."""

from ..models import Bodega, ProductoSerial, db, utcnow
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from .contexto import sucursales_autorizadas


class ErrorSerial(ValueError):
    codigo = "serial_invalido"


class ServicioSeriales:
    def __init__(self, usuario):
        self.usuario = usuario
        if not usuario.empresa_id or usuario.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def listar(self, *, producto_id=None, bodega_id=None, estado=None, buscar=None):
        self._exigir("stock.ver")
        sucursales_ids = {s.id for s in sucursales_autorizadas(self.usuario)}
        bodegas = db.select(Bodega.id).where(
            Bodega.empresa_id == self.usuario.empresa_id,
            Bodega.sucursal_id.in_(sucursales_ids),
        )
        consulta = db.select(ProductoSerial).where(
            ProductoSerial.empresa_id == self.usuario.empresa_id,
            ProductoSerial.bodega_id.in_(bodegas),
        )
        if producto_id:
            consulta = consulta.where(ProductoSerial.producto_id == producto_id)
        if bodega_id:
            consulta = consulta.where(ProductoSerial.bodega_id == bodega_id)
        if estado:
            consulta = consulta.where(ProductoSerial.estado == estado)
        if buscar:
            consulta = consulta.where(ProductoSerial.numero_serial.ilike(f"%{buscar.strip()}%"))
        return list(db.session.scalars(consulta.order_by(ProductoSerial.creado_en.desc())))

    def cambiar_estado(self, serial_id, estado):
        self._exigir("stock.ajuste")
        if estado not in {"disponible", "devuelto", "danado", "perdido"}:
            raise ErrorSerial("El estado solicitado no es válido")
        serial = self._obtener(serial_id, bloquear=True)
        if serial.estado in {"reservado"} or serial.venta_item_id or serial.transferencia_item_id:
            raise ErrorSerial("El serial está asociado a una venta o transferencia")
        if serial.estado == "salido" and estado not in {"devuelto", "danado"}:
            raise ErrorSerial("Un serial vendido sólo puede devolverse o marcarse dañado")
        serial.estado = estado
        if estado in {"disponible", "devuelto"}:
            serial.fecha_salida = None
        registrar_auditoria(
            accion="serial.estado_cambiado",
            modulo="inventario",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo="ProductoSerial",
            entidad_id=serial.id,
            datos_nuevos={"estado": estado, "numero_serial": serial.numero_serial},
        )
        db.session.commit()
        return serial

    def _obtener(self, serial_id, bloquear=False):
        consulta = db.select(ProductoSerial).where(
            ProductoSerial.id == serial_id,
            ProductoSerial.empresa_id == self.usuario.empresa_id,
        )
        serial = db.session.scalar(consulta.with_for_update() if bloquear else consulta)
        if not serial:
            raise PermissionError("Serial no autorizado")
        bodegas_ids = {
            b.id
            for b in db.session.scalars(
                db.select(Bodega).where(
                    Bodega.empresa_id == self.usuario.empresa_id,
                    Bodega.sucursal_id.in_({s.id for s in sucursales_autorizadas(self.usuario)}),
                )
            )
        }
        if serial.bodega_id not in bodegas_ids:
            raise PermissionError("Serial no autorizado")
        return serial

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.usuario, permiso, empresa_id=self.usuario.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)
