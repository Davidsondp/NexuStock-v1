"""Reglas de negocio del catálogo de productos."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError

from ..models import Inventario, Movimiento, PresentacionProducto, Producto, Proveedor, db
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from .perfiles_empresa import tiene_capacidad


class ErrorProducto(ValueError):
    pass


class LimiteProductosAlcanzado(ErrorProducto):
    pass


class ServicioProductos:
    def __init__(self, usuario):
        self.usuario = usuario

    def listar(self, *, busqueda=None, incluir_inactivos=False):
        self._exigir("productos.ver")
        consulta = db.select(Producto).where(
            Producto.empresa_id == self.usuario.empresa_id,
            Producto.eliminado.is_(False),
        )
        if not incluir_inactivos:
            consulta = consulta.where(Producto.activo.is_(True))
        if busqueda:
            patron = f"%{busqueda.strip()}%"
            consulta = consulta.where(
                db.or_(
                    Producto.nombre.ilike(patron),
                    Producto.codigo.ilike(patron),
                    Producto.codigo_barras.ilike(patron),
                )
            )
        return list(db.session.scalars(consulta.order_by(Producto.nombre)))

    def obtener(self, producto_id: int) -> Producto:
        self._exigir("productos.ver")
        producto = db.session.scalar(
            db.select(Producto).where(
                Producto.id == producto_id,
                Producto.empresa_id == self.usuario.empresa_id,
                Producto.eliminado.is_(False),
            )
        )
        if not producto:
            raise PermissionError("Producto no encontrado en la empresa")
        return producto

    def crear(self, *, confirmar=True, **datos) -> Producto:
        self._exigir("productos.crear")
        self._validar_limite()
        try:
            producto = Producto(empresa_id=self.usuario.empresa_id)
            self._asignar(producto, datos)
            db.session.add(producto)
            db.session.flush()
            self._sincronizar_caja(producto)
            self._auditar(producto, "creado")
            if confirmar:
                db.session.commit()
            else:
                db.session.flush()
            return producto
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorProducto("El código o código de barras ya está registrado") from exc
        except Exception:
            db.session.rollback()
            raise

    def editar(self, producto_id: int, *, confirmar=True, **datos) -> Producto:
        self._exigir("productos.editar")
        producto = self.obtener(producto_id)
        try:
            anteriores = {
                "codigo": producto.codigo,
                "nombre": producto.nombre,
                "precio_venta": str(producto.precio_venta),
            }
            self._asignar(producto, datos)
            self._sincronizar_caja(producto)
            self._auditar(producto, "editado", anteriores)
            if confirmar:
                db.session.commit()
            else:
                db.session.flush()
            return producto
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorProducto("El código o código de barras ya está registrado") from exc
        except Exception:
            db.session.rollback()
            raise

    def desactivar(self, producto_id: int) -> Producto:
        self._exigir("productos.eliminar")
        producto = self.obtener(producto_id)
        producto.activo = False
        self._auditar(producto, "desactivado")
        db.session.commit()
        return producto

    def reactivar(self, producto_id: int) -> Producto:
        self._exigir("productos.eliminar")

        producto = self.obtener(producto_id)
        producto.activo = True

        self._auditar(producto, "reactivado")

        db.session.commit()

        return producto

    def eliminar_logicamente(self, producto_id: int) -> Producto:
        self._exigir("productos.eliminar")
        producto = self.obtener(producto_id)
        tiene_historial = db.session.scalar(
            db.select(
                db.exists().where(
                    Movimiento.empresa_id == self.usuario.empresa_id,
                    Movimiento.producto_id == producto.id,
                )
            )
        )
        tiene_saldo = db.session.scalar(
            db.select(
                db.exists().where(
                    Inventario.empresa_id == self.usuario.empresa_id,
                    Inventario.producto_id == producto.id,
                    db.or_(Inventario.cantidad > 0, Inventario.cantidad_reservada > 0),
                )
            )
        )
        if tiene_historial or tiene_saldo:
            raise ErrorProducto("El producto tiene stock o historial; solo puede desactivarse")
        producto.soft_delete()
        producto.activo = False
        self._auditar(producto, "eliminado")
        db.session.commit()
        return producto

    def _asignar(self, producto, datos):
        self._validar_capacidades(datos)

        if "campos_personalizados" in datos:
            producto.campos_personalizados = self._campos_personalizados(
                datos.get("campos_personalizados")
            )

        codigo = (datos.get("codigo", producto.codigo) or "").strip().upper()
        nombre = (datos.get("nombre", producto.nombre) or "").strip()
        if not codigo or not nombre:
            raise ErrorProducto("Código y nombre son obligatorios")
        try:
            numeros = {
                campo: Decimal(str(datos.get(campo, getattr(producto, campo, None) or valor)))
                for campo, valor in {
                    "unidades_por_caja": 1,
                    "costo_referencia": 0,
                    "precio_venta": 0,
                    "tasa_impuesto": "0.19",
                    "stock_minimo": 0,
                    "punto_reorden": 0,
                }.items()
            }
            if "stock_maximo" in datos:
                stock_maximo = (
                    Decimal(str(datos["stock_maximo"]))
                    if datos.get("stock_maximo") not in (None, "")
                    else None
                )
            else:
                stock_maximo = producto.stock_maximo
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ErrorProducto("Uno de los valores numéricos no es válido") from exc
        if any(valor < 0 for valor in numeros.values()) or numeros["unidades_por_caja"] <= 0:
            raise ErrorProducto("Los valores numéricos deben ser válidos y no negativos")
        if stock_maximo is not None and stock_maximo < numeros["stock_minimo"]:
            raise ErrorProducto("El stock máximo no puede ser menor al stock mínimo")
        proveedor_id = datos.get("proveedor_principal_id", producto.proveedor_principal_id)
        if proveedor_id:
            proveedor = db.session.scalar(
                db.select(Proveedor).where(
                    Proveedor.id == int(proveedor_id),
                    Proveedor.empresa_id == self.usuario.empresa_id,
                    Proveedor.activo.is_(True),
                    Proveedor.eliminado.is_(False),
                )
            )
            if not proveedor:
                raise PermissionError("Proveedor fuera del ámbito empresarial")
        producto.codigo, producto.nombre = codigo, nombre
        if "codigo_barras" in datos:
            producto.codigo_barras = (datos.get("codigo_barras") or "").strip() or None
        producto.proveedor_principal_id = int(proveedor_id) if proveedor_id else None
        for campo in ("descripcion", "categoria", "subcategoria", "marca", "unidad_medida"):
            if campo in datos:
                setattr(
                    producto,
                    campo,
                    (datos[campo] or "").strip()
                    or ("unidad" if campo == "unidad_medida" else None),
                )
        for campo, valor in numeros.items():
            setattr(producto, campo, valor)
        producto.stock_maximo = stock_maximo
        for campo in (
            "incluye_iva",
            "requiere_serial",
            "controla_lotes",
            "controla_vencimiento",
        ):
            if campo in datos:
                setattr(
                    producto,
                    campo,
                    bool(datos[campo]),
                )

        if producto.controla_vencimiento:
            producto.controla_lotes = True

    @staticmethod
    def _campos_personalizados(valor):
        if valor in (None, ""):
            return {}
        if not isinstance(valor, dict):
            raise ErrorProducto("Los campos personalizados deben ser un objeto")
        if len(valor) > 20:
            raise ErrorProducto("Se permiten hasta 20 campos personalizados por producto")
        resultado = {}
        for clave, contenido in valor.items():
            nombre = str(clave or "").strip()
            if not nombre or len(nombre) > 60:
                raise ErrorProducto("El nombre de un campo personalizado no es válido")
            if isinstance(contenido, (dict, list)):
                raise ErrorProducto("Los valores personalizados deben ser simples")
            texto = str(contenido if contenido is not None else "").strip()
            if len(texto) > 500:
                raise ErrorProducto("Un valor personalizado supera 500 caracteres")
            resultado[nombre] = texto
        return resultado

    def _sincronizar_caja(
        self,
        producto: Producto,
    ) -> None:
        factor = Decimal(producto.unidades_por_caja or 1)

        caja = db.session.scalar(
            db.select(PresentacionProducto).where(
                PresentacionProducto.empresa_id == self.usuario.empresa_id,
                PresentacionProducto.producto_id == producto.id,
                PresentacionProducto.codigo == "CAJA",
            )
        )

        if factor <= 1:
            if caja is not None:
                caja.activa = False
            return

        if caja is None:
            caja = PresentacionProducto(
                empresa_id=self.usuario.empresa_id,
                producto_id=producto.id,
                codigo="CAJA",
                nombre="Caja",
                abreviatura="cj",
                factor_base=factor,
                activa=True,
            )
            db.session.add(caja)
            return

        caja.nombre = "Caja"
        caja.abreviatura = "cj"
        caja.factor_base = factor
        caja.activa = True

    def _validar_capacidades(self, datos):
        solicita_lotes = bool(datos.get("controla_lotes"))
        solicita_vencimiento = bool(datos.get("controla_vencimiento"))

        if solicita_lotes and not tiene_capacidad(
            self.usuario.empresa,
            "control_lotes",
        ):
            raise ErrorProducto("El control de lotes no está " "disponible para esta empresa")

        if solicita_vencimiento and not tiene_capacidad(
            self.usuario.empresa,
            "control_vencimientos",
        ):
            raise ErrorProducto(
                "El control de vencimientos " "no está disponible para " "esta empresa"
            )

    def _validar_limite(self):
        limite = self.usuario.empresa.suscripcion_actual.plan.limite_productos
        if limite is None:
            return
        cantidad = db.session.scalar(
            db.select(db.func.count(Producto.id)).where(
                Producto.empresa_id == self.usuario.empresa_id, Producto.eliminado.is_(False)
            )
        )
        if cantidad >= limite:
            raise LimiteProductosAlcanzado(
                "Se alcanzó el límite de artículos únicos del plan. Las "
                "cantidades disponibles de cada artículo no consumen capacidad adicional."
            )

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.usuario, permiso, empresa_id=self.usuario.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)

    def _auditar(self, producto, accion, anteriores=None):
        registrar_auditoria(
            accion=f"producto.{accion}",
            modulo="productos",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo="Producto",
            entidad_id=producto.id,
            datos_anteriores=anteriores,
            datos_nuevos={
                "codigo": producto.codigo,
                "nombre": producto.nombre,
                "activo": producto.activo,
            },
        )
