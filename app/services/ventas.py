"""Ventas con reserva y confirmación atómicas."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError

from ..models import (
    Bodega,
    Cliente,
    Inventario,
    PresentacionProducto,
    Producto,
    ProductoSerial,
    Venta,
    VentaItem,
    db,
    utcnow,
)
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from .contexto import ContextoOperacion, sucursales_autorizadas
from .inventario import ServicioInventario, StockInsuficiente, _cantidad_positiva

DOS = Decimal("0.01")


class ErrorVenta(ValueError):
    codigo = "venta_invalida"


class EstadoVentaInvalido(ErrorVenta):
    codigo = "estado_venta_invalido"


def _dinero(valor, nombre):
    try:
        resultado = Decimal(str(valor)).quantize(DOS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ErrorVenta(f"{nombre} no es válido") from exc
    if resultado < 0:
        raise ErrorVenta(f"{nombre} no puede ser negativo")
    return resultado


class ServicioVentas:
    def __init__(self, usuario):
        self.usuario = usuario
        if not usuario.empresa_id or usuario.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def listar(self, estado=None):
        self._exigir("ventas.ver")
        q = db.select(Venta).where(Venta.empresa_id == self.usuario.empresa_id)
        if estado:
            q = q.where(Venta.estado == estado)
        return list(db.session.scalars(q.order_by(Venta.creado_en.desc())))

    def obtener(self, venta_id, bloquear=False):
        self._exigir("ventas.ver")
        q = db.select(Venta).where(
            Venta.id == venta_id, Venta.empresa_id == self.usuario.empresa_id
        )
        venta = db.session.scalar(q.with_for_update() if bloquear else q)
        if not venta:
            raise PermissionError("Venta no autorizada")
        return venta

    def crear(
        self,
        *,
        numero,
        bodega_id,
        items,
        cliente_id=None,
        moneda="CLP",
        observaciones=None,
        confirmar_transaccion=True,
    ):
        self._exigir("ventas.crear")
        numero = (numero or "").strip().upper()
        if not numero or not isinstance(items, list) or not items:
            raise ErrorVenta("El número y los items son obligatorios")
        bodega = self._bodega(bodega_id)
        if cliente_id and not db.session.scalar(
            db.select(Cliente).where(
                Cliente.id == cliente_id,
                Cliente.empresa_id == self.usuario.empresa_id,
                Cliente.activo.is_(True),
                Cliente.eliminado.is_(False),
            )
        ):
            raise PermissionError("Cliente fuera del ámbito empresarial")
        try:
            venta = Venta(
                empresa_id=self.usuario.empresa_id,
                cliente_id=cliente_id,
                bodega_id=bodega.id,
                creada_por_id=self.usuario.id,
                numero=numero,
                moneda=(moneda or "CLP").upper(),
                observaciones=(observaciones or "").strip() or None,
            )
            db.session.add(venta)
            db.session.flush()
            vistos = set()
            for datos in items:
                producto = self._producto(int(datos.get("producto_id", 0)))
                if producto.id in vistos:
                    raise ErrorVenta("No se puede repetir un producto")
                vistos.add(producto.id)
                valores = self._preparar_item(
                    producto,
                    datos,
                )
                item = VentaItem(
                    empresa_id=self.usuario.empresa_id,
                    producto_id=producto.id,
                    **valores,
                )
                venta.items.append(item)
                db.session.flush()
                self._asociar_seriales(item, producto, bodega.id, datos.get("seriales") or [])
            venta.descuento = sum(
                (Decimal(item.descuento) for item in venta.items),
                Decimal("0"),
            )
            venta.impuesto = sum(
                (Decimal(item.impuesto) for item in venta.items),
                Decimal("0"),
            )
            venta.subtotal = sum(
                (
                    Decimal(item.total) + Decimal(item.descuento) - Decimal(item.impuesto)
                    for item in venta.items
                ),
                Decimal("0"),
            )
            venta.total = venta.subtotal - venta.descuento + venta.impuesto
            db.session.flush()
            self._auditar(venta, "borrador_creado")
            db.session.commit() if confirmar_transaccion else db.session.flush()
            return venta
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorVenta("El número de venta ya existe") from exc
        except Exception:
            db.session.rollback()
            raise

    def reservar(self, venta_id, *, confirmar_transaccion=True):
        self._exigir("ventas.reservar")
        venta = self.obtener(venta_id, True)
        if venta.estado != "borrador":
            raise EstadoVentaInvalido("Solo se reserva una venta en borrador")
        try:
            for item in venta.items:
                inv = self._inventario(venta.bodega_id, item.producto_id)
                if Decimal(inv.cantidad) - Decimal(inv.cantidad_reservada) < Decimal(item.cantidad):
                    raise StockInsuficiente("Stock disponible insuficiente para reservar")
                inv.cantidad_reservada = Decimal(inv.cantidad_reservada) + Decimal(item.cantidad)
                for serial in item.seriales:
                    if serial.estado != "disponible":
                        raise ErrorVenta(f"El serial {serial.numero_serial} ya no está disponible")
                    serial.estado = "reservado"
            venta.estado = "reservada"
            self._auditar(venta, "reservada")
            db.session.commit() if confirmar_transaccion else db.session.flush()
            return venta
        except Exception:
            db.session.rollback()
            raise

    def confirmar(self, venta_id, *, confirmar_transaccion=True):
        self._exigir("ventas.confirmar")
        venta = self.obtener(venta_id, True)
        if venta.estado != "reservada":
            raise EstadoVentaInvalido("La venta debe estar reservada para confirmarse")
        bodega = self._bodega(venta.bodega_id)
        contexto = ContextoOperacion(self.usuario.empresa_id, bodega.sucursal, bodega)
        try:
            for item in venta.items:
                inv = self._inventario(venta.bodega_id, item.producto_id)
                if Decimal(inv.cantidad_reservada) < Decimal(item.cantidad):
                    raise ErrorVenta("La reserva de inventario está incompleta")
                inv.cantidad_reservada = Decimal(inv.cantidad_reservada) - Decimal(item.cantidad)
                db.session.flush()
                ServicioInventario(self.usuario, contexto).salida(
                    producto_id=item.producto_id,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario,
                    motivo=f"Venta {venta.numero}",
                    referencia_tipo="venta",
                    referencia_id=venta.id,
                    confirmar=False,
                )
                for serial in item.seriales:
                    if serial.estado != "reservado":
                        raise ErrorVenta(f"El serial {serial.numero_serial} no está reservado")
                    serial.estado = "salido"
                    serial.fecha_salida = utcnow()
            venta.estado = "confirmada"
            venta.confirmada_en = utcnow()
            self._auditar(venta, "confirmada")
            db.session.commit() if confirmar_transaccion else db.session.flush()
            return venta
        except Exception:
            db.session.rollback()
            raise

    def cancelar(self, venta_id, motivo):
        self._exigir("ventas.cancelar")
        venta = self.obtener(venta_id, True)
        motivo = (motivo or "").strip()
        if venta.estado not in {"borrador", "reservada"}:
            raise EstadoVentaInvalido("Una venta confirmada no puede cancelarse")
        if not motivo:
            raise ErrorVenta("El motivo de cancelación es obligatorio")
        try:
            if venta.estado == "reservada":
                for item in venta.items:
                    inv = self._inventario(venta.bodega_id, item.producto_id)
                    if Decimal(inv.cantidad_reservada) < Decimal(item.cantidad):
                        raise ErrorVenta("La reserva de inventario está incompleta")
                    inv.cantidad_reservada = Decimal(inv.cantidad_reservada) - Decimal(
                        item.cantidad
                    )
                    for serial in item.seriales:
                        if serial.estado == "reservado":
                            serial.estado = "disponible"
            for item in venta.items:
                for serial in item.seriales:
                    serial.venta_item_id = None
            venta.estado = "cancelada"
            venta.cancelada_en = utcnow()
            venta.motivo_cancelacion = motivo
            self._auditar(venta, "cancelada")
            db.session.commit()
            return venta
        except Exception:
            db.session.rollback()
            raise

    def _preparar_item(
        self,
        producto,
        datos,
    ):
        cantidad_presentacion = _cantidad_positiva(datos.get("cantidad"))

        valor_precio = datos.get("precio_unitario")

        presentacion_id = datos.get("presentacion_id")
        presentacion = None

        if presentacion_id not in (
            None,
            "",
        ):
            try:
                presentacion_id = int(presentacion_id)
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ErrorVenta("La presentación no es válida") from exc

            presentacion = db.session.scalar(
                db.select(PresentacionProducto).where(
                    PresentacionProducto.id == presentacion_id,
                    PresentacionProducto.empresa_id == self.usuario.empresa_id,
                    PresentacionProducto.producto_id == producto.id,
                    PresentacionProducto.activa.is_(True),
                )
            )

            if presentacion is None:
                raise ErrorVenta("La presentación no pertenece " "al producto o está inactiva")

        factor = Decimal(presentacion.factor_base if presentacion else 1).quantize(
            Decimal("0.001"),
            rounding=ROUND_HALF_UP,
        )

        if valor_precio is None:
            valor_precio = Decimal(producto.precio_venta) * factor

        precio_presentacion = _dinero(
            valor_precio,
            "Precio de presentación",
        )

        cantidad_base = (cantidad_presentacion * factor).quantize(
            Decimal("0.001"),
            rounding=ROUND_HALF_UP,
        )

        precio_base = (precio_presentacion / factor).quantize(
            DOS,
            rounding=ROUND_HALF_UP,
        )

        descuento = _dinero(
            datos.get("descuento", 0),
            "Descuento",
        )
        impuesto = _dinero(
            datos.get("impuesto", 0),
            "Impuesto",
        )

        bruto = (cantidad_presentacion * precio_presentacion).quantize(
            DOS,
            rounding=ROUND_HALF_UP,
        )

        if descuento > bruto:
            raise ErrorVenta("El descuento supera " "el subtotal del item")

        return {
            "presentacion_id": (presentacion.id if presentacion else None),
            "presentacion_codigo": (presentacion.codigo if presentacion else None),
            "presentacion_nombre": (presentacion.nombre if presentacion else None),
            "presentacion_abreviatura": (presentacion.abreviatura if presentacion else None),
            "cantidad_presentacion": cantidad_presentacion,
            "factor_conversion": factor,
            "precio_presentacion": precio_presentacion,
            "cantidad": cantidad_base,
            "precio_unitario": precio_base,
            "descuento": descuento,
            "impuesto": impuesto,
            "total": bruto - descuento + impuesto,
        }

    def _inventario(self, bodega_id, producto_id):
        inv = db.session.scalar(
            db.select(Inventario)
            .where(
                Inventario.empresa_id == self.usuario.empresa_id,
                Inventario.bodega_id == bodega_id,
                Inventario.producto_id == producto_id,
            )
            .with_for_update()
        )
        if not inv:
            raise StockInsuficiente("El producto no tiene existencias en la bodega")
        return inv

    def _asociar_seriales(self, item, producto, bodega_id, numeros):
        numeros = [str(numero).strip() for numero in numeros if str(numero).strip()]
        cantidad = Decimal(item.cantidad)
        if producto.requiere_serial:
            if cantidad != cantidad.to_integral_value() or len(numeros) != int(cantidad):
                raise ErrorVenta("Debe seleccionar un serial disponible por cada unidad")
            if len(numeros) != len(set(numeros)):
                raise ErrorVenta("Los seriales no pueden repetirse")
        elif numeros:
            raise ErrorVenta("Este producto no utiliza números de serie")
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
                )
                .with_for_update()
            )
        )
        if len(seriales) != len(numeros):
            raise ErrorVenta("Uno o más seriales no existen o no están disponibles")
        for serial in seriales:
            serial.venta_item_id = item.id

    def _producto(self, id):
        p = db.session.scalar(
            db.select(Producto).where(
                Producto.id == id,
                Producto.empresa_id == self.usuario.empresa_id,
                Producto.activo.is_(True),
                Producto.eliminado.is_(False),
            )
        )
        if not p:
            raise PermissionError("Producto fuera del ámbito empresarial")
        return p

    def _bodega(self, id):
        ids = {s.id for s in sucursales_autorizadas(self.usuario)}
        b = db.session.scalar(
            db.select(Bodega).where(
                Bodega.id == id,
                Bodega.empresa_id == self.usuario.empresa_id,
                Bodega.sucursal_id.in_(ids),
                Bodega.activa.is_(True),
                Bodega.eliminado.is_(False),
            )
        )
        if not b:
            raise PermissionError("Bodega no autorizada")
        return b

    def _exigir(self, p):
        d = evaluar_permiso(self.usuario, p, empresa_id=self.usuario.empresa_id)
        if not d.permitido:
            raise PermissionError(d.mensaje)

    def _auditar(self, v, a):
        registrar_auditoria(
            accion=f"venta.{a}",
            modulo="ventas",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo="Venta",
            entidad_id=v.id,
            datos_nuevos={"numero": v.numero, "estado": v.estado},
        )
