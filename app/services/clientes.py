"""Reglas de negocio para clientes multiempresa."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from ..models import Cliente, Venta, db
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from ..validaciones import normalizar_rut, normalizar_telefono


class ErrorCliente(ValueError):
    pass


class ServicioClientes:
    def __init__(self, usuario):
        self.usuario = usuario

    def listar(
        self,
        *,
        busqueda=None,
        incluir_inactivos=False,
    ):
        self._exigir("clientes.ver")

        consulta = db.select(Cliente).where(
            Cliente.empresa_id == self.usuario.empresa_id,
            Cliente.eliminado.is_(False),
        )

        if not incluir_inactivos:
            consulta = consulta.where(Cliente.activo.is_(True))

        if busqueda and busqueda.strip():
            patron = f"%{busqueda.strip()}%"

            consulta = consulta.where(
                db.or_(
                    Cliente.nombre.ilike(patron),
                    Cliente.identificacion_fiscal.ilike(patron),
                    Cliente.email.ilike(patron),
                    Cliente.telefono.ilike(patron),
                )
            )

        return list(db.session.scalars(consulta.order_by(Cliente.nombre)))

    def obtener(self, cliente_id: int) -> Cliente:
        self._exigir("clientes.ver")

        cliente = db.session.scalar(
            db.select(Cliente).where(
                Cliente.id == cliente_id,
                Cliente.empresa_id == self.usuario.empresa_id,
                Cliente.eliminado.is_(False),
            )
        )

        if not cliente:
            raise PermissionError("Cliente no encontrado en la empresa")

        return cliente

    def crear(self, **datos) -> Cliente:
        self._exigir("clientes.crear")

        try:
            cliente = Cliente(
                empresa_id=self.usuario.empresa_id,
            )

            self._asignar(cliente, datos)

            db.session.add(cliente)
            db.session.flush()

            self._auditar(cliente, "creado")
            db.session.commit()

            return cliente
        except IntegrityError as exc:
            db.session.rollback()

            raise ErrorCliente("Ya existe un cliente con esa " "identificación fiscal") from exc
        except Exception:
            db.session.rollback()
            raise

    def editar(
        self,
        cliente_id: int,
        **datos,
    ) -> Cliente:
        self._exigir("clientes.editar")

        cliente = self.obtener(cliente_id)

        anteriores = {
            "nombre": cliente.nombre,
            "identificacion_fiscal": cliente.identificacion_fiscal,
            "email": cliente.email,
            "telefono": cliente.telefono,
            "direccion": cliente.direccion,
        }

        try:
            self._asignar(cliente, datos)
            self._auditar(
                cliente,
                "editado",
                anteriores,
            )
            db.session.commit()

            return cliente
        except IntegrityError as exc:
            db.session.rollback()

            raise ErrorCliente("Ya existe un cliente con esa " "identificación fiscal") from exc
        except Exception:
            db.session.rollback()
            raise

    def desactivar(self, cliente_id: int) -> Cliente:
        self._exigir("clientes.eliminar")

        cliente = self.obtener(cliente_id)
        cliente.activo = False

        self._auditar(cliente, "desactivado")
        db.session.commit()

        return cliente

    def reactivar(self, cliente_id: int) -> Cliente:
        self._exigir("clientes.eliminar")

        cliente = self.obtener(cliente_id)
        cliente.activo = True

        self._auditar(cliente, "reactivado")
        db.session.commit()

        return cliente

    def eliminar_logicamente(
        self,
        cliente_id: int,
    ) -> Cliente:
        self._exigir("clientes.eliminar")

        cliente = self.obtener(cliente_id)

        tiene_ventas = db.session.scalar(
            db.select(
                db.exists().where(
                    Venta.empresa_id == self.usuario.empresa_id,
                    Venta.cliente_id == cliente.id,
                )
            )
        )

        if tiene_ventas:
            raise ErrorCliente("El cliente tiene ventas asociadas; " "solo puede desactivarse")

        cliente.soft_delete()
        cliente.activo = False

        self._auditar(cliente, "eliminado")
        db.session.commit()

        return cliente

    def _asignar(self, cliente, datos):
        nombre = (datos.get("nombre", cliente.nombre) or "").strip()

        if not nombre:
            raise ErrorCliente("El nombre es obligatorio")

        cliente.nombre = nombre

        if "identificacion_fiscal" in datos:
            try:
                cliente.identificacion_fiscal = normalizar_rut(datos.get("identificacion_fiscal"))
            except ValueError as exc:
                raise ErrorCliente(str(exc)) from exc
        if "telefono" in datos:
            try:
                cliente.telefono = normalizar_telefono(datos.get("telefono"))
            except ValueError as exc:
                raise ErrorCliente(str(exc)) from exc
        for campo in ("email", "direccion"):
            if campo in datos:
                valor = datos.get(campo)

                setattr(
                    cliente,
                    campo,
                    (str(valor).strip() if valor is not None else "") or None,
                )

    def _exigir(self, permiso):
        decision = evaluar_permiso(
            self.usuario,
            permiso,
            empresa_id=self.usuario.empresa_id,
        )

        if not decision.permitido:
            raise PermissionError(decision.mensaje)

    def _auditar(
        self,
        cliente,
        accion,
        anteriores=None,
    ):
        registrar_auditoria(
            accion=f"cliente.{accion}",
            modulo="clientes",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo="Cliente",
            entidad_id=cliente.id,
            datos_anteriores=anteriores,
            datos_nuevos={
                "nombre": cliente.nombre,
                "activo": cliente.activo,
            },
        )
