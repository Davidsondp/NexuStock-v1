"""Administración multiempresa de sucursales, bodegas y asignaciones."""

from sqlalchemy.exc import IntegrityError

from ..models import Bodega, Inventario, Sucursal, Transferencia, Usuario, UsuarioSucursal, db
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from .contexto import limpiar_contexto


class ErrorUbicacion(ValueError):
    pass


class LimiteSucursalesAlcanzado(ErrorUbicacion):
    pass


class LimiteBodegasAlcanzado(ErrorUbicacion):
    pass


class ServicioUbicaciones:
    def __init__(self, usuario):
        self.usuario = usuario

    def listar_sucursales(self, incluir_inactivas=False):
        self._exigir("sucursales.ver")
        consulta = db.select(Sucursal).where(
            Sucursal.empresa_id == self.usuario.empresa_id, Sucursal.eliminado.is_(False)
        )
        if not incluir_inactivas:
            consulta = consulta.where(Sucursal.activa.is_(True))
        return list(db.session.scalars(consulta.order_by(Sucursal.nombre)))

    def listar_bodegas(self, sucursal_id=None, incluir_inactivas=False):
        self._exigir("bodegas.ver")
        consulta = db.select(Bodega).where(
            Bodega.empresa_id == self.usuario.empresa_id, Bodega.eliminado.is_(False)
        )
        if sucursal_id is not None:
            consulta = consulta.where(Bodega.sucursal_id == sucursal_id)
        if not incluir_inactivas:
            consulta = consulta.where(Bodega.activa.is_(True))
        return list(db.session.scalars(consulta.order_by(Bodega.nombre)))

    def crear_sucursal(
        self,
        *,
        codigo,
        nombre,
        direccion=None,
        ciudad=None,
        telefono=None,
        crear_bodega_principal=True,
    ):
        self._exigir("sucursales.crear")
        self._validar_limite_sucursales()
        try:
            sucursal = Sucursal(
                empresa_id=self.usuario.empresa_id,
                codigo=self._codigo(codigo),
                nombre=self._nombre(nombre),
                direccion=direccion,
                ciudad=ciudad,
                telefono=telefono,
            )
            db.session.add(sucursal)
            db.session.flush()
            if crear_bodega_principal:
                self._validar_limite_bodegas()
                db.session.add(
                    Bodega(
                        empresa_id=self.usuario.empresa_id,
                        sucursal_id=sucursal.id,
                        codigo=f"{sucursal.codigo}-PRINCIPAL",
                        nombre=f"Bodega principal - {sucursal.nombre}",
                    )
                )
            # El creador recibe acceso; no se entrega acceso automático a otros usuarios.
            db.session.add(
                UsuarioSucursal(
                    empresa_id=self.usuario.empresa_id,
                    usuario_id=self.usuario.id,
                    sucursal_id=sucursal.id,
                )
            )
            self._auditar("sucursal.creada", "Sucursal", sucursal.id)
            db.session.commit()
            return sucursal
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorUbicacion("El código de sucursal ya existe") from exc
        except Exception:
            db.session.rollback()
            raise

    def crear_bodega(self, *, sucursal_id, codigo, nombre, descripcion=None):
        self._exigir("bodegas.crear")
        self._validar_limite_bodegas()
        sucursal = self._sucursal(sucursal_id)
        try:
            bodega = Bodega(
                empresa_id=self.usuario.empresa_id,
                sucursal_id=sucursal.id,
                codigo=self._codigo(codigo),
                nombre=self._nombre(nombre),
                descripcion=descripcion,
            )
            db.session.add(bodega)
            db.session.flush()
            self._auditar("bodega.creada", "Bodega", bodega.id)
            db.session.commit()
            return bodega
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorUbicacion("El código de bodega ya existe") from exc
        except Exception:
            db.session.rollback()
            raise

    def editar_sucursal(
        self,
        sucursal_id,
        **cambios,
    ):
        self._exigir("sucursales.editar")
        sucursal = self._sucursal(sucursal_id)

        permitidos = {
            "codigo",
            "nombre",
            "direccion",
            "ciudad",
            "telefono",
        }

        try:
            for campo, valor in cambios.items():
                if campo not in permitidos:
                    continue

                if campo == "codigo":
                    valor = self._codigo(valor)
                elif campo == "nombre":
                    valor = self._nombre(valor)
                else:
                    valor = self._texto_opcional(valor)

                setattr(sucursal, campo, valor)

            db.session.flush()
            self._auditar(
                "sucursal.editada",
                "Sucursal",
                sucursal.id,
            )
            db.session.commit()
            return sucursal
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorUbicacion("El codigo de sucursal ya existe") from exc
        except Exception:
            db.session.rollback()
            raise

    def editar_bodega(
        self,
        bodega_id,
        **cambios,
    ):
        self._exigir("bodegas.editar")
        bodega = self._bodega(bodega_id)

        permitidos = {
            "codigo",
            "nombre",
            "descripcion",
        }

        try:
            for campo, valor in cambios.items():
                if campo not in permitidos:
                    continue

                if campo == "codigo":
                    valor = self._codigo(valor)
                elif campo == "nombre":
                    valor = self._nombre(valor)
                else:
                    valor = self._texto_opcional(valor)

                setattr(bodega, campo, valor)

            db.session.flush()
            self._auditar(
                "bodega.editada",
                "Bodega",
                bodega.id,
            )
            db.session.commit()
            return bodega
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorUbicacion("El codigo de bodega ya existe") from exc
        except Exception:
            db.session.rollback()
            raise

    def reactivar_sucursal(
        self,
        sucursal_id,
    ):
        self._exigir("sucursales.editar")
        sucursal = self._sucursal(sucursal_id)

        if sucursal.activa:
            return sucursal

        sucursal.activa = True

        bodegas = [bodega for bodega in sucursal.bodegas if not bodega.eliminado]

        if bodegas and not any(bodega.activa for bodega in bodegas):
            bodegas[0].activa = True

        self._auditar(
            "sucursal.reactivada",
            "Sucursal",
            sucursal.id,
        )
        db.session.commit()
        return sucursal

    def reactivar_bodega(
        self,
        bodega_id,
    ):
        self._exigir("bodegas.editar")
        bodega = self._bodega(bodega_id)

        if not bodega.sucursal.activa:
            raise ErrorUbicacion("Primero debes reactivar la sucursal")

        if bodega.activa:
            return bodega

        bodega.activa = True
        self._auditar(
            "bodega.reactivada",
            "Bodega",
            bodega.id,
        )
        db.session.commit()
        return bodega

    def asignar_usuario(self, *, usuario_id, sucursal_id, es_principal=False):
        self._exigir("usuarios.editar")
        usuario = db.session.scalar(
            db.select(Usuario).where(
                Usuario.id == usuario_id,
                Usuario.empresa_id == self.usuario.empresa_id,
                Usuario.eliminado.is_(False),
            )
        )
        sucursal = self._sucursal(sucursal_id)
        if not usuario:
            raise PermissionError("Usuario fuera del ámbito empresarial")
        asignacion = db.session.scalar(
            db.select(UsuarioSucursal).where(
                UsuarioSucursal.empresa_id == self.usuario.empresa_id,
                UsuarioSucursal.usuario_id == usuario.id,
                UsuarioSucursal.sucursal_id == sucursal.id,
            )
        )
        if asignacion is None:
            asignacion = UsuarioSucursal(
                empresa_id=self.usuario.empresa_id, usuario_id=usuario.id, sucursal_id=sucursal.id
            )
            db.session.add(asignacion)
        if es_principal:
            for otra in db.session.scalars(
                db.select(UsuarioSucursal).where(
                    UsuarioSucursal.empresa_id == self.usuario.empresa_id,
                    UsuarioSucursal.usuario_id == usuario.id,
                )
            ):
                otra.es_principal = False
        asignacion.es_principal = bool(es_principal)
        db.session.flush()
        self._auditar("sucursal.usuario_asignado", "UsuarioSucursal", asignacion.id)
        db.session.commit()
        return asignacion

    def desasignar_usuario(self, *, usuario_id, sucursal_id):
        self._exigir("usuarios.editar")
        asignacion = db.session.scalar(
            db.select(UsuarioSucursal).where(
                UsuarioSucursal.empresa_id == self.usuario.empresa_id,
                UsuarioSucursal.usuario_id == usuario_id,
                UsuarioSucursal.sucursal_id == sucursal_id,
            )
        )
        if not asignacion:
            raise PermissionError("Asignación no encontrada")
        cantidad = db.session.scalar(
            db.select(db.func.count(UsuarioSucursal.id)).where(
                UsuarioSucursal.empresa_id == self.usuario.empresa_id,
                UsuarioSucursal.usuario_id == usuario_id,
            )
        )
        if cantidad <= 1:
            raise ErrorUbicacion("El usuario debe conservar al menos una sucursal")
        db.session.delete(asignacion)
        db.session.commit()

    def desactivar_bodega(self, bodega_id):
        self._exigir("bodegas.desactivar")
        bodega = self._bodega(bodega_id)
        self._validar_bodega_sin_operacion(bodega)
        activas = db.session.scalar(
            db.select(db.func.count(Bodega.id)).where(
                Bodega.empresa_id == self.usuario.empresa_id,
                Bodega.sucursal_id == bodega.sucursal_id,
                Bodega.activa.is_(True),
                Bodega.eliminado.is_(False),
            )
        )
        if activas <= 1:
            raise ErrorUbicacion("La sucursal debe conservar al menos una bodega activa")
        bodega.activa = False
        self._auditar("bodega.desactivada", "Bodega", bodega.id)
        db.session.commit()
        limpiar_contexto()
        return bodega

    def desactivar_sucursal(self, sucursal_id):
        self._exigir("sucursales.desactivar")
        sucursal = self._sucursal(sucursal_id)
        activas = db.session.scalar(
            db.select(db.func.count(Sucursal.id)).where(
                Sucursal.empresa_id == self.usuario.empresa_id,
                Sucursal.activa.is_(True),
                Sucursal.eliminado.is_(False),
            )
        )
        if activas <= 1:
            raise ErrorUbicacion("La empresa debe conservar al menos una sucursal activa")
        for bodega in sucursal.bodegas:
            self._validar_bodega_sin_operacion(bodega)
        sucursal.activa = False
        for bodega in sucursal.bodegas:
            bodega.activa = False
        self._auditar("sucursal.desactivada", "Sucursal", sucursal.id)
        db.session.commit()
        limpiar_contexto()
        return sucursal

    def _validar_bodega_sin_operacion(self, bodega):
        saldo = db.session.scalar(
            db.select(
                db.exists().where(
                    Inventario.empresa_id == self.usuario.empresa_id,
                    Inventario.bodega_id == bodega.id,
                    db.or_(Inventario.cantidad > 0, Inventario.cantidad_reservada > 0),
                )
            )
        )
        pendiente = db.session.scalar(
            db.select(
                db.exists().where(
                    Transferencia.empresa_id == self.usuario.empresa_id,
                    Transferencia.estado.in_(("solicitada", "en_transito")),
                    db.or_(
                        Transferencia.bodega_origen_id == bodega.id,
                        Transferencia.bodega_destino_id == bodega.id,
                    ),
                )
            )
        )
        if saldo or pendiente:
            raise ErrorUbicacion("La bodega tiene stock o transferencias pendientes")

    def _validar_limite_sucursales(self):
        limite = self.usuario.empresa.suscripcion_actual.plan.limite_sucursales
        cantidad = db.session.scalar(
            db.select(db.func.count(Sucursal.id)).where(
                Sucursal.empresa_id == self.usuario.empresa_id, Sucursal.eliminado.is_(False)
            )
        )
        if limite is not None and cantidad >= limite:
            raise LimiteSucursalesAlcanzado("Límite de sucursales alcanzado")

    def _validar_limite_bodegas(self):
        limite = self.usuario.empresa.suscripcion_actual.plan.limite_bodegas
        cantidad = db.session.scalar(
            db.select(db.func.count(Bodega.id)).where(
                Bodega.empresa_id == self.usuario.empresa_id, Bodega.eliminado.is_(False)
            )
        )
        if limite is not None and cantidad >= limite:
            raise LimiteBodegasAlcanzado("Límite de bodegas alcanzado")

    def _sucursal(self, id_):
        entidad = db.session.scalar(
            db.select(Sucursal).where(
                Sucursal.id == id_,
                Sucursal.empresa_id == self.usuario.empresa_id,
                Sucursal.eliminado.is_(False),
            )
        )
        if not entidad:
            raise PermissionError("Sucursal fuera del ámbito empresarial")
        return entidad

    def _bodega(self, id_):
        entidad = db.session.scalar(
            db.select(Bodega).where(
                Bodega.id == id_,
                Bodega.empresa_id == self.usuario.empresa_id,
                Bodega.eliminado.is_(False),
            )
        )
        if not entidad:
            raise PermissionError("Bodega fuera del ámbito empresarial")
        return entidad

    @staticmethod
    def _texto_opcional(valor):
        if valor is None:
            return None

        valor = str(valor).strip()
        return valor or None

    @staticmethod
    def _codigo(valor):
        valor = (valor or "").strip().upper()
        if not valor:
            raise ErrorUbicacion("El código es obligatorio")
        return valor

    @staticmethod
    def _nombre(valor):
        valor = (valor or "").strip()
        if not valor:
            raise ErrorUbicacion("El nombre es obligatorio")
        return valor

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.usuario, permiso, empresa_id=self.usuario.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)

    def _auditar(self, accion, tipo, entidad_id):
        registrar_auditoria(
            accion=accion,
            modulo="ubicaciones",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo=tipo,
            entidad_id=entidad_id,
        )
