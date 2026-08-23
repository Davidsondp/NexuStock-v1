"""Flujo transaccional de transferencias entre bodegas."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from ..models import (
    Bodega,
    Movimiento,
    Producto,
    ProductoSerial,
    Transferencia,
    TransferenciaItem,
    UsuarioSucursal,
    db,
    utcnow,
)
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from .contexto import ContextoOperacion, sucursales_autorizadas
from .inventario import ServicioInventario, _cantidad_positiva


class ErrorTransferencia(ValueError):
    pass


class EstadoTransferenciaInvalido(ErrorTransferencia):
    pass


class ServicioTransferencias:
    def __init__(self, usuario):
        self.usuario = usuario
        if not usuario.empresa_id or usuario.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def crear(
        self,
        *,
        numero: str,
        bodega_origen_id: int,
        bodega_destino_id: int,
        items: list[dict],
        observaciones=None,
    ) -> Transferencia:
        self._exigir("transferencias.crear")
        origen = self._bodega_autorizada(bodega_origen_id)
        destino = self._bodega_autorizada(bodega_destino_id)
        if origen.id == destino.id:
            raise ErrorTransferencia("Las bodegas deben ser diferentes")
        if not (numero or "").strip() or not items:
            raise ErrorTransferencia("Número e items son obligatorios")
        try:
            transferencia = Transferencia(
                empresa_id=self.usuario.empresa_id,
                numero=numero.strip().upper(),
                bodega_origen_id=origen.id,
                bodega_destino_id=destino.id,
                estado="borrador",
                observaciones=observaciones,
            )
            db.session.add(transferencia)
            db.session.flush()
            productos_vistos = set()
            for datos in items:
                producto_id = int(datos["producto_id"])
                if producto_id in productos_vistos:
                    raise ErrorTransferencia("No se puede repetir un producto")
                producto = db.session.scalar(
                    db.select(Producto).where(
                        Producto.id == producto_id,
                        Producto.empresa_id == self.usuario.empresa_id,
                        Producto.activo.is_(True),
                        Producto.eliminado.is_(False),
                    )
                )
                if not producto:
                    raise PermissionError("Producto fuera del ámbito empresarial")
                productos_vistos.add(producto_id)
                item = TransferenciaItem(
                    empresa_id=self.usuario.empresa_id,
                    transferencia_id=transferencia.id,
                    producto_id=producto_id,
                    cantidad_solicitada=_cantidad_positiva(datos["cantidad"]),
                    cantidad_despachada=0,
                    cantidad_recibida=0,
                )
                db.session.add(item)
                db.session.flush()
                self._asociar_seriales(
                    item,
                    producto,
                    origen.id,
                    datos.get("seriales") or [],
                )
            self._auditar(transferencia, "creada")
            db.session.commit()
            return transferencia
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorTransferencia("El número de transferencia ya existe") from exc
        except Exception:
            db.session.rollback()
            raise

    def listar(self, estado: str | None = None) -> list[Transferencia]:
        """Lista únicamente transferencias de bodegas autorizadas al usuario."""
        self._exigir("transferencias.ver")
        sucursales_ids = {s.id for s in sucursales_autorizadas(self.usuario)}
        bodegas_ids = db.select(Bodega.id).where(
            Bodega.empresa_id == self.usuario.empresa_id,
            Bodega.sucursal_id.in_(sucursales_ids),
        )
        consulta = db.select(Transferencia).where(
            Transferencia.empresa_id == self.usuario.empresa_id,
            Transferencia.bodega_origen_id.in_(bodegas_ids),
            Transferencia.bodega_destino_id.in_(bodegas_ids),
        )
        if estado:
            if estado not in {"borrador", "solicitada", "en_transito", "recibida", "cancelada"}:
                raise ErrorTransferencia("El estado de transferencia no es válido")
            consulta = consulta.where(Transferencia.estado == estado)
        return list(db.session.scalars(consulta.order_by(Transferencia.creado_en.desc())))

    def obtener(self, transferencia_id: int) -> Transferencia:
        self._exigir("transferencias.ver")
        return self._obtener(transferencia_id)

    def solicitar(self, transferencia_id: int) -> Transferencia:
        transferencia = self._obtener(transferencia_id, bloquear=True)
        self._exigir("transferencias.crear")
        self._cambiar_estado(transferencia, "borrador", "solicitada")
        transferencia.solicitada_por_id = self.usuario.id
        transferencia.fecha_solicitud = utcnow()
        for item in transferencia.items:
            for serial in item.seriales:
                if serial.estado != "disponible":
                    raise ErrorTransferencia(
                        f"El serial {serial.numero_serial} ya no está disponible"
                    )
                serial.estado = "reservado"
        return self._confirmar(transferencia, "solicitada")

    def despachar(
        self, transferencia_id: int, cantidades: dict[int, Decimal] | None = None
    ) -> Transferencia:
        transferencia = self._obtener(transferencia_id, bloquear=True)
        self._exigir("transferencias.despachar")
        self._cambiar_estado(transferencia, "solicitada", "en_transito")
        origen = self._bodega_autorizada(transferencia.bodega_origen_id)
        contexto = ContextoOperacion(self.usuario.empresa_id, origen.sucursal, origen)
        try:
            for item in transferencia.items:
                cantidad = (
                    _cantidad_positiva(cantidades[item.id])
                    if cantidades and item.id in cantidades
                    else Decimal(item.cantidad_solicitada)
                )
                if cantidad > item.cantidad_solicitada:
                    raise ErrorTransferencia("No se puede despachar más de lo solicitado")
                ServicioInventario(self.usuario, contexto).transferencia_salida(
                    producto_id=item.producto_id,
                    cantidad=cantidad,
                    motivo=f"Despacho transferencia {transferencia.numero}",
                    referencia_id=transferencia.id,
                    confirmar=False,
                )
                item.cantidad_despachada = cantidad
                if item.seriales and cantidad != item.cantidad_solicitada:
                    raise ErrorTransferencia(
                        "Los productos serializados deben despacharse por la cantidad solicitada"
                    )
            transferencia.estado = "en_transito"
            transferencia.despachada_por_id = self.usuario.id
            transferencia.fecha_despacho = utcnow()
            self._auditar(transferencia, "despachada")
            db.session.commit()
            return transferencia
        except Exception:
            db.session.rollback()
            raise

    def recibir(
        self, transferencia_id: int, cantidades: dict[int, Decimal] | None = None
    ) -> Transferencia:
        transferencia = self._obtener(transferencia_id, bloquear=True)
        self._exigir("transferencias.recibir")
        self._cambiar_estado(transferencia, "en_transito", "recibida")
        destino = self._bodega_autorizada(transferencia.bodega_destino_id)
        contexto = ContextoOperacion(self.usuario.empresa_id, destino.sucursal, destino)
        try:
            for item in transferencia.items:
                cantidad = (
                    _cantidad_positiva(cantidades[item.id])
                    if cantidades and item.id in cantidades
                    else Decimal(item.cantidad_despachada)
                )
                if cantidad > item.cantidad_despachada:
                    raise ErrorTransferencia("No se puede recibir más de lo despachado")
                movimiento_salida = db.session.scalar(
                    db.select(Movimiento).where(
                        Movimiento.empresa_id == self.usuario.empresa_id,
                        Movimiento.referencia_tipo == "transferencia",
                        Movimiento.referencia_id == transferencia.id,
                        Movimiento.producto_id == item.producto_id,
                        Movimiento.bodega_id == transferencia.bodega_origen_id,
                    )
                )
                ServicioInventario(self.usuario, contexto).transferencia_entrada(
                    producto_id=item.producto_id,
                    cantidad=cantidad,
                    costo_unitario=movimiento_salida.costo_unitario,
                    motivo=f"Recepción transferencia {transferencia.numero}",
                    referencia_id=transferencia.id,
                    confirmar=False,
                )
                item.cantidad_recibida = cantidad
                if item.seriales and cantidad != item.cantidad_despachada:
                    raise ErrorTransferencia(
                        "Los productos serializados deben recibirse por la cantidad despachada"
                    )
                for serial in item.seriales:
                    if serial.estado != "reservado":
                        raise ErrorTransferencia(
                            f"El serial {serial.numero_serial} no está reservado"
                        )
                    serial.bodega_id = destino.id
                    serial.estado = "disponible"
                    serial.transferencia_item_id = None
            transferencia.estado = "recibida"
            transferencia.recibida_por_id = self.usuario.id
            transferencia.fecha_recepcion = utcnow()
            self._auditar(transferencia, "recibida")
            db.session.commit()
            return transferencia
        except Exception:
            db.session.rollback()
            raise

    def cancelar(self, transferencia_id: int, motivo: str) -> Transferencia:
        transferencia = self._obtener(transferencia_id, bloquear=True)
        self._exigir("transferencias.crear")
        if transferencia.estado not in {"borrador", "solicitada"}:
            raise EstadoTransferenciaInvalido("Solo se cancela antes del despacho")
        transferencia.estado = "cancelada"
        transferencia.observaciones = motivo
        for item in transferencia.items:
            for serial in item.seriales:
                if serial.estado == "reservado":
                    serial.estado = "disponible"
                serial.transferencia_item_id = None
        return self._confirmar(transferencia, "cancelada")

    def _asociar_seriales(self, item, producto, bodega_id, numeros):
        numeros = [str(numero).strip() for numero in numeros if str(numero).strip()]
        cantidad = Decimal(item.cantidad_solicitada)
        if producto.requiere_serial:
            if cantidad != cantidad.to_integral_value() or len(numeros) != int(cantidad):
                raise ErrorTransferencia("Debe seleccionar un serial por cada unidad")
            if len(numeros) != len(set(numeros)):
                raise ErrorTransferencia("Los seriales no pueden repetirse")
        elif numeros:
            raise ErrorTransferencia("Este producto no utiliza números de serie")
        if not numeros:
            return
        seriales = list(
            db.session.scalars(
                db.select(ProductoSerial)
                .where(
                    ProductoSerial.empresa_id == self.usuario.empresa_id,
                    ProductoSerial.producto_id == producto.id,
                    ProductoSerial.bodega_id == bodega_id,
                    ProductoSerial.numero_serial.in_(numeros),
                    ProductoSerial.estado == "disponible",
                    ProductoSerial.venta_item_id.is_(None),
                    ProductoSerial.transferencia_item_id.is_(None),
                )
                .with_for_update()
            )
        )
        if len(seriales) != len(numeros):
            raise ErrorTransferencia("Uno o más seriales no están disponibles en la bodega")
        for serial in seriales:
            serial.transferencia_item_id = item.id

    def _exigir(self, permiso: str) -> None:
        decision = evaluar_permiso(self.usuario, permiso, empresa_id=self.usuario.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)

    def _bodega_autorizada(self, bodega_id: int) -> Bodega:
        sucursales_ids = {s.id for s in sucursales_autorizadas(self.usuario)}
        bodega = db.session.scalar(
            db.select(Bodega).where(
                Bodega.id == bodega_id,
                Bodega.empresa_id == self.usuario.empresa_id,
                Bodega.sucursal_id.in_(sucursales_ids),
                Bodega.activa.is_(True),
                Bodega.eliminado.is_(False),
            )
        )
        if not bodega:
            raise PermissionError("Bodega no autorizada")
        return bodega

    def _obtener(self, transferencia_id: int, bloquear=False) -> Transferencia:
        consulta = db.select(Transferencia).where(
            Transferencia.id == transferencia_id,
            Transferencia.empresa_id == self.usuario.empresa_id,
        )
        if bloquear:
            consulta = consulta.with_for_update()
        transferencia = db.session.scalar(consulta)
        if not transferencia:
            raise PermissionError("Transferencia no autorizada")
        self._bodega_autorizada(transferencia.bodega_origen_id)
        self._bodega_autorizada(transferencia.bodega_destino_id)
        return transferencia

    @staticmethod
    def _cambiar_estado(transferencia, esperado, nuevo):
        if transferencia.estado != esperado:
            raise EstadoTransferenciaInvalido(
                f"La transferencia debe estar {esperado} para pasar a {nuevo}"
            )
        transferencia.estado = nuevo

    def _auditar(self, transferencia, accion):
        registrar_auditoria(
            accion=f"transferencia.{accion}",
            modulo="transferencias",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo="Transferencia",
            entidad_id=transferencia.id,
            datos_nuevos={"estado": transferencia.estado},
        )

    def _confirmar(self, transferencia, accion):
        try:
            self._auditar(transferencia, accion)
            db.session.commit()
            return transferencia
        except Exception:
            db.session.rollback()
            raise
