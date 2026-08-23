"""Reglas de negocio para proveedores multiempresa."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError

from ..models import OrdenCompra, Producto, Proveedor, db
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from ..validaciones import normalizar_rut, normalizar_telefono


class ErrorProveedor(ValueError):
    pass


class ServicioProveedores:
    def __init__(self, usuario):
        self.usuario = usuario

    def listar(
        self,
        *,
        busqueda=None,
        incluir_inactivos=False,
    ):
        self._exigir("proveedores.ver")

        consulta = db.select(Proveedor).where(
            Proveedor.empresa_id == self.usuario.empresa_id,
            Proveedor.eliminado.is_(False),
        )

        if not incluir_inactivos:
            consulta = consulta.where(Proveedor.activo.is_(True))

        if busqueda:
            patron = f"%{busqueda.strip()}%"

            consulta = consulta.where(
                db.or_(
                    Proveedor.nombre.ilike(patron),
                    Proveedor.identificacion_fiscal.ilike(patron),
                    Proveedor.email.ilike(patron),
                    Proveedor.ciudad.ilike(patron),
                )
            )

        return list(db.session.scalars(consulta.order_by(Proveedor.nombre)))

    def obtener(self, proveedor_id: int) -> Proveedor:
        self._exigir("proveedores.ver")

        proveedor = db.session.scalar(
            db.select(Proveedor).where(
                Proveedor.id == proveedor_id,
                Proveedor.empresa_id == self.usuario.empresa_id,
                Proveedor.eliminado.is_(False),
            )
        )

        if not proveedor:
            raise PermissionError("Proveedor no encontrado en la empresa")

        return proveedor

    def crear(self, **datos) -> Proveedor:
        self._exigir("proveedores.crear")
        try:
            proveedor = Proveedor(empresa_id=self.usuario.empresa_id)
            self._asignar(proveedor, datos)
            db.session.add(proveedor)
            db.session.flush()
            self._auditar(proveedor, "creado")
            db.session.commit()
            return proveedor
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorProveedor("Ya existe un proveedor con esa identificación fiscal") from exc
        except Exception:
            db.session.rollback()
            raise

    def editar(self, proveedor_id: int, **datos) -> Proveedor:
        self._exigir("proveedores.editar")
        proveedor = self.obtener(proveedor_id)
        try:
            anteriores = {
                "nombre": proveedor.nombre,
                "identificacion_fiscal": proveedor.identificacion_fiscal,
            }
            self._asignar(proveedor, datos)
            self._auditar(proveedor, "editado", anteriores)
            db.session.commit()
            return proveedor
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorProveedor("Ya existe un proveedor con esa identificación fiscal") from exc
        except Exception:
            db.session.rollback()
            raise

    def desactivar(self, proveedor_id: int) -> Proveedor:
        self._exigir("proveedores.eliminar")
        proveedor = self.obtener(proveedor_id)
        proveedor.activo = False
        self._auditar(proveedor, "desactivado")
        db.session.commit()
        return proveedor

    def reactivar(self, proveedor_id: int) -> Proveedor:
        self._exigir("proveedores.eliminar")

        proveedor = self.obtener(proveedor_id)
        proveedor.activo = True

        self._auditar(proveedor, "reactivado")

        db.session.commit()

        return proveedor

    def eliminar_logicamente(self, proveedor_id: int) -> Proveedor:
        self._exigir("proveedores.eliminar")
        proveedor = self.obtener(proveedor_id)
        tiene_historial = db.session.scalar(
            db.select(
                db.exists().where(
                    OrdenCompra.empresa_id == self.usuario.empresa_id,
                    OrdenCompra.proveedor_id == proveedor.id,
                )
            )
        )
        tiene_productos = db.session.scalar(
            db.select(
                db.exists().where(
                    Producto.empresa_id == self.usuario.empresa_id,
                    Producto.proveedor_principal_id == proveedor.id,
                    Producto.eliminado.is_(False),
                )
            )
        )
        if tiene_historial or tiene_productos:
            raise ErrorProveedor(
                "El proveedor tiene productos o compras asociadas; solo puede desactivarse"
            )
        proveedor.soft_delete()
        proveedor.activo = False
        self._auditar(proveedor, "eliminado")
        db.session.commit()
        return proveedor

    def _asignar(self, proveedor, datos):
        nombre = (datos.get("nombre", proveedor.nombre) or "").strip()
        if not nombre:
            raise ErrorProveedor("El nombre es obligatorio")
        try:
            compra_minima = Decimal(str(datos.get("compra_minima", proveedor.compra_minima or 0)))
            dias_entrega = int(
                datos.get(
                    "dias_entrega",
                    proveedor.dias_entrega if proveedor.dias_entrega is not None else 7,
                )
            )
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ErrorProveedor("Compra mínima o días de entrega inválidos") from exc
        if compra_minima < 0 or dias_entrega < 0:
            raise ErrorProveedor("Los valores comerciales no pueden ser negativos")
        proveedor.nombre = nombre
        if "identificacion_fiscal" in datos:
            try:
                proveedor.identificacion_fiscal = normalizar_rut(datos.get("identificacion_fiscal"))
            except ValueError as exc:
                raise ErrorProveedor(str(exc)) from exc

        if "pais" in datos:
            pais = (datos.get("pais") or "CL").strip().upper()

            if len(pais) != 2 or not pais.isalpha():
                raise ErrorProveedor("El país debe usar un código de dos letras")

            proveedor.pais = pais

        for campo in (
            "email",
            "direccion",
            "ciudad",
            "sitio_web",
            "condiciones_pago",
            "observaciones",
        ):
            if campo in datos:
                setattr(
                    proveedor,
                    campo,
                    (datos[campo] or "").strip() or None,
                )
        if "telefono" in datos:
            try:
                proveedor.telefono = normalizar_telefono(datos.get("telefono"))
            except ValueError as exc:
                raise ErrorProveedor(str(exc)) from exc

        proveedor.dias_entrega, proveedor.compra_minima = dias_entrega, compra_minima

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.usuario, permiso, empresa_id=self.usuario.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)

    def _auditar(self, proveedor, accion, anteriores=None):
        registrar_auditoria(
            accion=f"proveedor.{accion}",
            modulo="proveedores",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo="Proveedor",
            entidad_id=proveedor.id,
            datos_anteriores=anteriores,
            datos_nuevos={"nombre": proveedor.nombre, "activo": proveedor.activo},
        )
