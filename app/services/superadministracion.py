"""Administración global sin acceso operativo a inventario empresarial."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import platform

from sqlalchemy.exc import IntegrityError

from ..catalogo_planes import PLANES_PUBLICOS
from ..models import (
    Auditoria,
    DocumentoFacturacionSaaS,
    Empresa,
    Pago,
    PlanSaaS,
    SolicitudContratoEmpresarial,
    Suscripcion,
    Usuario,
    db,
    utcnow,
)
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria


class ErrorSuperAdministracion(ValueError):
    codigo = "superadministracion_invalida"


class ServicioSuperAdministracion:
    def __init__(self, actor):
        self.actor = actor
        if actor.rol != "super_admin" or actor.empresa_id is not None:
            raise PermissionError("Se requiere una cuenta Super Admin global")

    def resumen(self):
        self._exigir("superadmin.dashboard")
        return {
            "empresas": db.session.scalar(
                db.select(db.func.count(Empresa.id)).where(Empresa.eliminado.is_(False))
            ),
            "empresas_activas": db.session.scalar(
                db.select(db.func.count(Empresa.id)).where(
                    Empresa.estado == "activa", Empresa.eliminado.is_(False)
                )
            ),
            "usuarios_empresariales": db.session.scalar(
                db.select(db.func.count(Usuario.id)).where(
                    Usuario.empresa_id.is_not(None), Usuario.eliminado.is_(False)
                )
            ),
            "suscripciones_activas": db.session.scalar(
                db.select(db.func.count(Suscripcion.id)).where(
                    Suscripcion.estado.in_(("prueba", "activa"))
                )
            ),
            "pagos_confirmados": db.session.scalar(
                db.select(db.func.count(Pago.id)).where(Pago.estado == "pagado")
            ),
            "contratos_empresariales_pendientes": db.session.scalar(
                db.select(db.func.count(SolicitudContratoEmpresarial.id)).where(
                    SolicitudContratoEmpresarial.estado.in_(("nueva", "contactada", "cotizada"))
                )
            ),
            "ingresos_confirmados": str(
                Decimal(
                    db.session.scalar(
                        db.select(db.func.coalesce(db.func.sum(Pago.monto), 0)).where(
                            Pago.estado == "pagado"
                        )
                    )
                    or 0
                )
            ),
        }

    def listar_solicitudes_empresariales(self, *, estado=None):
        self._exigir("superadmin.suscripciones")
        consulta = db.select(SolicitudContratoEmpresarial)
        if estado:
            consulta = consulta.where(SolicitudContratoEmpresarial.estado == str(estado).lower())
        return list(
            db.session.scalars(
                consulta.order_by(SolicitudContratoEmpresarial.creado_en.desc()).limit(500)
            )
        )

    def actualizar_solicitud_empresarial(self, solicitud_id, *, estado, observacion=None):
        self._exigir("superadmin.suscripciones")
        estado = str(estado or "").lower()
        if estado not in {"nueva", "contactada", "cotizada", "contratada", "descartada"}:
            raise ErrorSuperAdministracion("Estado de contrato no admitido")
        solicitud = db.session.get(SolicitudContratoEmpresarial, solicitud_id)
        if not solicitud:
            raise ErrorSuperAdministracion("Solicitud empresarial no encontrada")
        solicitud.estado = estado
        solicitud.observacion_interna = str(observacion or "").strip()[:3000] or None
        solicitud.atendida_en = utcnow() if estado != "nueva" else None
        registrar_auditoria(
            accion="contrato_empresarial.actualizado",
            modulo="superadministracion",
            usuario_id=self.actor.id,
            entidad_tipo="SolicitudContratoEmpresarial",
            entidad_id=solicitud.id,
            datos_nuevos={"estado": estado},
        )
        db.session.commit()
        return solicitud

    def listar_empresas(self, *, estado=None, buscar=None):
        self._exigir("superadmin.empresas")
        q = db.select(Empresa).where(Empresa.eliminado.is_(False))
        if estado:
            if estado not in {"activa", "suspendida", "cancelada"}:
                raise ErrorSuperAdministracion("Estado inválido")
            q = q.where(Empresa.estado == estado)
        if buscar:
            patron = f"%{buscar.strip()}%"
            q = q.where(
                db.or_(
                    Empresa.nombre.ilike(patron),
                    Empresa.email.ilike(patron),
                    Empresa.identificacion_fiscal.ilike(patron),
                )
            )
        return list(db.session.scalars(q.order_by(Empresa.creado_en.desc()).limit(500)))

    def cambiar_estado_empresa(self, empresa_id, *, estado, motivo):
        self._exigir("superadmin.empresas")
        if estado not in {"activa", "suspendida", "cancelada"}:
            raise ErrorSuperAdministracion("Estado inválido")
        motivo = (motivo or "").strip()
        if estado != "activa" and not motivo:
            raise ErrorSuperAdministracion("El motivo es obligatorio")
        empresa = db.session.scalar(
            db.select(Empresa)
            .where(Empresa.id == empresa_id, Empresa.eliminado.is_(False))
            .with_for_update()
        )
        if not empresa:
            raise ErrorSuperAdministracion("Empresa no encontrada")
        anterior = empresa.estado
        empresa.estado = estado
        empresa.motivo_suspension = None if estado == "activa" else motivo
        # Cierra sesiones existentes de todos los usuarios de la empresa.
        for usuario in empresa.usuarios:
            usuario.version_sesion += 1
        self._auditar(
            "superadmin.empresa_estado",
            "Empresa",
            empresa.id,
            {"estado_anterior": anterior, "estado": estado, "motivo": motivo or None},
        )
        db.session.commit()
        return empresa

    def listar_planes(self, *, incluir_inactivos=True):
        self._exigir("superadmin.planes")
        q = db.select(PlanSaaS).where(PlanSaaS.codigo.in_(PLANES_PUBLICOS))
        if not incluir_inactivos:
            q = q.where(PlanSaaS.activo.is_(True))
        return list(db.session.scalars(q.order_by(PlanSaaS.orden, PlanSaaS.nombre)))

    def editar_plan(self, plan_id, **datos):
        self._exigir("superadmin.planes")
        plan = db.session.get(PlanSaaS, plan_id)
        if not plan or plan.codigo not in PLANES_PUBLICOS:
            raise ErrorSuperAdministracion("Plan no encontrado")
        permitidos = {
            "nombre",
            "descripcion",
            "precio_mensual",
            "precio_anual",
            "dias_prueba",
            "limite_productos",
            "limite_usuarios",
            "limite_movimientos_mes",
            "limite_sucursales",
            "limite_bodegas",
            "almacenamiento_mb",
            "funciones",
            "activo",
            "orden",
        }
        desconocidos = set(datos) - permitidos
        if desconocidos:
            raise ErrorSuperAdministracion(
                f"Campos de plan no editables: {', '.join(sorted(desconocidos))}"
            )
        anterior = self._plan_dict(plan)
        try:
            for campo in ("precio_mensual", "precio_anual"):
                if campo in datos:
                    valor = Decimal(str(datos[campo]))
                    if valor < 0:
                        raise ErrorSuperAdministracion("Los precios no pueden ser negativos")
                    setattr(plan, campo, valor)
            for campo in ("dias_prueba", "orden"):
                if campo in datos:
                    valor = int(datos[campo])
                    if valor < 0:
                        raise ErrorSuperAdministracion(f"{campo} no puede ser negativo")
                    setattr(plan, campo, valor)
            if "limite_productos" in datos:
                limite_productos = datos["limite_productos"]

                if limite_productos is None:
                    raise ErrorSuperAdministracion(
                        "El límite de artículos únicos es obligatorio " "en los planes comerciales"
                    )

                try:
                    limite_productos = int(limite_productos)
                except (TypeError, ValueError) as exc:
                    raise ErrorSuperAdministracion(
                        "El límite de artículos únicos debe ser " "un número entero"
                    ) from exc

                if limite_productos <= 0:
                    raise ErrorSuperAdministracion(
                        "El límite de artículos únicos debe ser " "mayor que cero"
                    )

                datos["limite_productos"] = limite_productos

            for campo in (
                "limite_productos",
                "limite_usuarios",
                "limite_movimientos_mes",
                "limite_sucursales",
                "limite_bodegas",
                "almacenamiento_mb",
            ):
                if campo in datos:
                    valor = None if datos[campo] is None else int(datos[campo])
                    if valor is not None and valor < 0:
                        raise ErrorSuperAdministracion("Los límites no pueden ser negativos")
                    setattr(plan, campo, valor)
            if "nombre" in datos:
                nombre = (datos["nombre"] or "").strip()
                if not nombre:
                    raise ErrorSuperAdministracion("El nombre es obligatorio")
                plan.nombre = nombre
            if "descripcion" in datos:
                plan.descripcion = (datos["descripcion"] or "").strip() or None
            if "activo" in datos:
                if not isinstance(datos["activo"], bool):
                    raise ErrorSuperAdministracion("activo debe ser booleano")
                if not datos["activo"] and db.session.scalar(
                    db.select(
                        db.exists().where(
                            Suscripcion.plan_id == plan.id,
                            Suscripcion.estado.in_(("prueba", "activa")),
                        )
                    )
                ):
                    raise ErrorSuperAdministracion(
                        "No se desactiva un plan con suscripciones vigentes"
                    )
                plan.activo = datos["activo"]
            if "funciones" in datos:
                if not isinstance(datos["funciones"], dict) or any(
                    not isinstance(v, bool) for v in datos["funciones"].values()
                ):
                    raise ErrorSuperAdministracion("Las funciones deben ser un objeto de booleanos")
                plan.funciones = dict(datos["funciones"])
            if Decimal(plan.precio_mensual) <= 0 or Decimal(plan.precio_anual) <= 0:
                raise ErrorSuperAdministracion(
                    "Los planes comerciales deben tener precios positivos"
                )
            if plan.dias_prueba != 30:
                raise ErrorSuperAdministracion("Todos los planes deben conservar 30 días de prueba")
            self._auditar(
                "superadmin.plan_editado",
                "PlanSaaS",
                plan.id,
                {"anterior": anterior, "nuevo": self._plan_dict(plan)},
            )
            db.session.commit()
            return plan
        except (IntegrityError, InvalidOperation, TypeError, ValueError) as exc:
            db.session.rollback()
            if isinstance(exc, ErrorSuperAdministracion):
                raise
            raise ErrorSuperAdministracion("Datos de plan inválidos o duplicados") from exc

    def listar_suscripciones(self, *, empresa_id=None, estado=None):
        self._exigir("superadmin.suscripciones")
        q = db.select(Suscripcion)
        if empresa_id:
            q = q.where(Suscripcion.empresa_id == empresa_id)
        if estado:
            q = q.where(Suscripcion.estado == estado)
        return list(db.session.scalars(q.order_by(Suscripcion.creado_en.desc()).limit(1000)))

    def editar_suscripcion(
        self,
        suscripcion_id,
        *,
        plan_id=None,
        estado=None,
        renovacion_automatica=None,
        cancelar_al_fin_periodo=None,
        fecha_fin=None,
        motivo=None,
    ):
        """Corrección excepcional del propietario; nunca crea pagos ficticios."""
        self._exigir("superadmin.suscripciones")
        motivo = str(motivo or "").strip()
        if not motivo:
            raise ErrorSuperAdministracion("El motivo administrativo es obligatorio")
        suscripcion = db.session.scalar(
            db.select(Suscripcion).where(Suscripcion.id == suscripcion_id).with_for_update()
        )
        if not suscripcion:
            raise ErrorSuperAdministracion("Suscripción no encontrada")
        anterior = self._suscripcion_dict(suscripcion)
        if plan_id is not None:
            plan = db.session.get(PlanSaaS, int(plan_id))
            if not plan or not plan.activo:
                raise ErrorSuperAdministracion("Plan activo no encontrado")
            suscripcion.plan_id = plan.id
        if estado is not None:
            if estado not in {"prueba", "activa", "vencida", "suspendida", "cancelada"}:
                raise ErrorSuperAdministracion("Estado de suscripción inválido")
            suscripcion.estado = estado
            if estado == "cancelada":
                suscripcion.cancelada_en = utcnow()
                suscripcion.renovacion_automatica = False
        if renovacion_automatica is not None:
            if not isinstance(renovacion_automatica, bool):
                raise ErrorSuperAdministracion("renovacion_automatica debe ser booleano")
            if renovacion_automatica and suscripcion.metodo_pago_recurrente_estado != "activo":
                raise ErrorSuperAdministracion(
                    "No se puede activar la renovación sin un método recurrente verificado"
                )
            suscripcion.renovacion_automatica = renovacion_automatica
            if renovacion_automatica:
                suscripcion.cancelar_al_fin_periodo = False
        if cancelar_al_fin_periodo is not None:
            if not isinstance(cancelar_al_fin_periodo, bool):
                raise ErrorSuperAdministracion("cancelar_al_fin_periodo debe ser booleano")
            suscripcion.cancelar_al_fin_periodo = cancelar_al_fin_periodo
            if cancelar_al_fin_periodo:
                suscripcion.renovacion_automatica = False
        if fecha_fin is not None:
            try:
                suscripcion.fecha_fin = (
                    datetime.fromisoformat(str(fecha_fin)) if fecha_fin else None
                )
            except ValueError as exc:
                raise ErrorSuperAdministracion("fecha_fin debe usar formato ISO") from exc
            if suscripcion.fecha_fin and suscripcion.fecha_fin < suscripcion.fecha_inicio:
                raise ErrorSuperAdministracion("La fecha final no puede preceder al inicio")
            suscripcion.periodo_actual_fin = suscripcion.fecha_fin
        if suscripcion.estado in {"vencida", "suspendida", "cancelada"}:
            suscripcion.renovacion_automatica = False
        suscripcion.motivo_cancelacion = (
            motivo
            if suscripcion.estado in {"cancelada", "suspendida"}
            else suscripcion.motivo_cancelacion
        )
        self._auditar(
            "superadmin.suscripcion_editada",
            "Suscripcion",
            suscripcion.id,
            {"motivo": motivo, "anterior": anterior, "nuevo": self._suscripcion_dict(suscripcion)},
        )
        db.session.commit()
        return suscripcion

    def listar_documentos_facturacion(self, *, empresa_id=None, estado=None):
        self._exigir("superadmin.pagos")
        q = db.select(DocumentoFacturacionSaaS)
        if empresa_id:
            q = q.where(DocumentoFacturacionSaaS.empresa_id == empresa_id)
        if estado:
            if estado not in {"emitido", "anulado"}:
                raise ErrorSuperAdministracion("Estado documental inválido")
            q = q.where(DocumentoFacturacionSaaS.estado == estado)
        return list(
            db.session.scalars(q.order_by(DocumentoFacturacionSaaS.emitido_en.desc()).limit(1000))
        )

    def resumen_seguridad(self):
        self._exigir("superadmin.sistema")
        privilegiados = Usuario.rol.in_(("super_admin", "jefe"))
        total_privilegiados = (
            db.session.scalar(
                db.select(db.func.count(Usuario.id)).where(
                    privilegiados, Usuario.activo.is_(True), Usuario.eliminado.is_(False)
                )
            )
            or 0
        )
        con_2fa = (
            db.session.scalar(
                db.select(db.func.count(Usuario.id)).where(
                    privilegiados,
                    Usuario.activo.is_(True),
                    Usuario.eliminado.is_(False),
                    Usuario.two_factor_enabled.is_(True),
                )
            )
            or 0
        )
        return {
            "cuentas_privilegiadas": total_privilegiados,
            "cuentas_privilegiadas_con_2fa": con_2fa,
            "cobertura_2fa_pct": (
                round(con_2fa / total_privilegiados * 100, 1) if total_privilegiados else 100.0
            ),
            "usuarios_bloqueados": db.session.scalar(
                db.select(db.func.count(Usuario.id)).where(
                    Usuario.bloqueado_hasta > utcnow(), Usuario.eliminado.is_(False)
                )
            )
            or 0,
            "correos_no_verificados": db.session.scalar(
                db.select(db.func.count(Usuario.id)).where(
                    Usuario.email_verificado.is_(False),
                    Usuario.activo.is_(True),
                    Usuario.eliminado.is_(False),
                )
            )
            or 0,
            "pagos_en_incidencia": db.session.scalar(
                db.select(db.func.count(Pago.id)).where(Pago.estado == "incidencia")
            )
            or 0,
            "documentos_emitidos": db.session.scalar(
                db.select(db.func.count(DocumentoFacturacionSaaS.id)).where(
                    DocumentoFacturacionSaaS.estado == "emitido"
                )
            )
            or 0,
        }

    def listar_pagos(self, *, empresa_id=None, estado=None, proveedor=None):
        self._exigir("superadmin.pagos")
        q = db.select(Pago)
        if empresa_id:
            q = q.where(Pago.empresa_id == empresa_id)
        if estado:
            q = q.where(Pago.estado == estado)
        if proveedor:
            q = q.where(Pago.proveedor == proveedor.lower())
        return list(db.session.scalars(q.order_by(Pago.creado_en.desc()).limit(1000)))

    def listar_auditoria(self, *, empresa_id=None, accion=None, limite=200):
        self._exigir("superadmin.auditoria")
        q = db.select(Auditoria)
        if empresa_id is not None:
            q = q.where(Auditoria.empresa_id == empresa_id)
        if accion:
            q = q.where(Auditoria.accion == accion)
        return list(
            db.session.scalars(
                q.order_by(Auditoria.fecha.desc()).limit(min(max(int(limite), 1), 1000))
            )
        )

    def listar_usuarios(self, *, empresa_id=None, rol=None, estado=None, buscar=None):
        self._exigir("superadmin.usuarios")
        consulta = db.select(Usuario).where(Usuario.eliminado.is_(False))
        if empresa_id is not None:
            consulta = consulta.where(Usuario.empresa_id == empresa_id)
        if rol:
            if rol not in {"super_admin", "jefe", "supervisor", "empleado"}:
                raise ErrorSuperAdministracion("Rol inválido")
            consulta = consulta.where(Usuario.rol == rol)
        if estado == "activo":
            consulta = consulta.where(Usuario.activo.is_(True))
        elif estado == "inactivo":
            consulta = consulta.where(Usuario.activo.is_(False))
        elif estado:
            raise ErrorSuperAdministracion("Estado de usuario inválido")
        if buscar:
            patron = f"%{buscar.strip()}%"
            consulta = consulta.where(
                db.or_(
                    Usuario.nombre.ilike(patron),
                    Usuario.apellido.ilike(patron),
                    Usuario.email.ilike(patron),
                    Usuario.identificacion_fiscal.ilike(patron),
                    Usuario.telefono.ilike(patron),
                    Usuario.empresa.has(Empresa.nombre.ilike(patron)),
                )
            )
        return list(db.session.scalars(consulta.order_by(Usuario.creado_en.desc()).limit(1000)))

    def cambiar_estado_usuario(self, usuario_id, *, activo):
        self._exigir("superadmin.usuarios")
        if not isinstance(activo, bool):
            raise ErrorSuperAdministracion("activo debe ser booleano")
        usuario = db.session.get(Usuario, usuario_id)
        if not usuario or usuario.eliminado:
            raise ErrorSuperAdministracion("Usuario no encontrado")
        if usuario.id == self.actor.id and not activo:
            raise ErrorSuperAdministracion("No puedes desactivar tu propia cuenta")
        if usuario.rol == "super_admin" and not activo:
            restantes = db.session.scalar(
                db.select(db.func.count(Usuario.id)).where(
                    Usuario.rol == "super_admin",
                    Usuario.activo.is_(True),
                    Usuario.eliminado.is_(False),
                    Usuario.id != usuario.id,
                )
            )
            if not restantes:
                raise ErrorSuperAdministracion("Debe existir al menos un Super Admin activo")
        usuario.activo = activo
        usuario.version_sesion += 1
        if activo:
            usuario.intentos_fallidos = 0
            usuario.bloqueado_hasta = None
        self._auditar(
            "superadmin.usuario_estado",
            "Usuario",
            usuario.id,
            {"activo": activo, "empresa_id": usuario.empresa_id},
        )
        db.session.commit()
        return usuario

    def desbloquear_usuario(self, usuario_id):
        self._exigir("superadmin.usuarios")
        usuario = db.session.get(Usuario, usuario_id)
        if not usuario or usuario.eliminado:
            raise ErrorSuperAdministracion("Usuario no encontrado")
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        usuario.version_sesion += 1
        self._auditar("superadmin.usuario_desbloqueado", "Usuario", usuario.id, {})
        db.session.commit()
        return usuario

    def estado_sistema(self):
        self._exigir("superadmin.sistema")
        revision = None
        try:
            revision = db.session.scalar(db.text("SELECT version_num FROM alembic_version"))
        except Exception:
            db.session.rollback()
        return {
            "estado": "operativo",
            "base_datos": db.engine.dialect.name,
            "revision_migracion": revision,
            "python": platform.python_version(),
            "hora_utc": utcnow().isoformat(),
            "auditorias": db.session.scalar(db.select(db.func.count(Auditoria.id))),
            "usuarios_activos": db.session.scalar(
                db.select(db.func.count(Usuario.id)).where(Usuario.activo.is_(True))
            ),
            "empresas_activas": db.session.scalar(
                db.select(db.func.count(Empresa.id)).where(Empresa.estado == "activa")
            ),
            "seguridad": self.resumen_seguridad(),
        }

    @staticmethod
    def _suscripcion_dict(suscripcion):
        return {
            "plan_id": suscripcion.plan_id,
            "estado": suscripcion.estado,
            "ciclo": suscripcion.ciclo,
            "fecha_fin": suscripcion.fecha_fin.isoformat() if suscripcion.fecha_fin else None,
            "renovacion_automatica": suscripcion.renovacion_automatica,
            "cancelar_al_fin_periodo": suscripcion.cancelar_al_fin_periodo,
        }

    def analitica(self, *, meses=12):
        """Entrega indicadores globales agregados, sin exponer datos operativos."""
        self._exigir("superadmin.dashboard")
        try:
            meses = int(meses)
        except (TypeError, ValueError) as exc:
            raise ErrorSuperAdministracion("El período debe expresarse en meses") from exc
        if meses not in {6, 12, 24}:
            raise ErrorSuperAdministracion("El período debe ser de 6, 12 o 24 meses")

        ahora = utcnow()
        mes_actual = ahora.year * 12 + ahora.month - 1
        inicio_indice = mes_actual - meses + 1
        inicio_anterior_indice = inicio_indice - meses

        def inicio_mes(indice):
            return datetime(indice // 12, indice % 12 + 1, 1)

        inicio = inicio_mes(inicio_indice)
        inicio_anterior = inicio_mes(inicio_anterior_indice)
        fin = inicio_mes(mes_actual + 1)
        pagos = list(
            db.session.execute(
                db.select(
                    Pago.monto, Pago.fecha_confirmacion, Pago.fecha_pago, Pago.creado_en
                ).where(
                    Pago.estado == "pagado",
                    Pago.moneda == "CLP",
                    db.func.coalesce(Pago.fecha_confirmacion, Pago.fecha_pago, Pago.creado_en)
                    >= inicio_anterior,
                    db.func.coalesce(Pago.fecha_confirmacion, Pago.fecha_pago, Pago.creado_en)
                    < fin,
                )
            )
        )
        ingresos_por_mes = {indice: Decimal("0") for indice in range(inicio_indice, mes_actual + 1)}
        ingresos_periodo = Decimal("0")
        ingresos_anterior = Decimal("0")
        pagos_periodo = 0
        for monto, confirmada, pagada, creada in pagos:
            fecha = confirmada or pagada or creada
            indice = fecha.year * 12 + fecha.month - 1
            valor = Decimal(monto or 0)
            if indice >= inicio_indice:
                ingresos_periodo += valor
                pagos_periodo += 1
                if indice in ingresos_por_mes:
                    ingresos_por_mes[indice] += valor
            else:
                ingresos_anterior += valor

        empresas_por_mes = {indice: 0 for indice in range(inicio_indice, mes_actual + 1)}
        for (creada,) in db.session.execute(
            db.select(Empresa.creado_en).where(
                Empresa.eliminado.is_(False),
                Empresa.creado_en >= inicio,
                Empresa.creado_en < fin,
            )
        ):
            indice = creada.year * 12 + creada.month - 1
            if indice in empresas_por_mes:
                empresas_por_mes[indice] += 1

        crecimiento = None
        if ingresos_anterior > 0:
            crecimiento = float(
                ((ingresos_periodo - ingresos_anterior) / ingresos_anterior * 100).quantize(
                    Decimal("0.1")
                )
            )

        planes = [
            {"nombre": nombre, "cantidad": cantidad}
            for nombre, cantidad in db.session.execute(
                db.select(PlanSaaS.nombre, db.func.count(Suscripcion.id))
                .join(Suscripcion, Suscripcion.plan_id == PlanSaaS.id)
                .where(Suscripcion.estado.in_(("prueba", "activa")))
                .group_by(PlanSaaS.id, PlanSaaS.nombre)
                .order_by(db.func.count(Suscripcion.id).desc(), PlanSaaS.nombre)
            )
        ]
        empresas_total = (
            db.session.scalar(
                db.select(db.func.count(Empresa.id)).where(Empresa.eliminado.is_(False))
            )
            or 0
        )
        empresas_activas = (
            db.session.scalar(
                db.select(db.func.count(Empresa.id)).where(
                    Empresa.estado == "activa", Empresa.eliminado.is_(False)
                )
            )
            or 0
        )

        nombres_meses = (
            "Ene",
            "Feb",
            "Mar",
            "Abr",
            "May",
            "Jun",
            "Jul",
            "Ago",
            "Sep",
            "Oct",
            "Nov",
            "Dic",
        )
        serie = []
        for indice in range(inicio_indice, mes_actual + 1):
            fecha = inicio_mes(indice)
            serie.append(
                {
                    "periodo": f"{fecha.year:04d}-{fecha.month:02d}",
                    "etiqueta": f"{nombres_meses[fecha.month - 1]} {str(fecha.year)[2:]}",
                    "ingresos": str(ingresos_por_mes[indice]),
                    "nuevas_empresas": empresas_por_mes[indice],
                }
            )

        return {
            "meses": meses,
            "moneda": "CLP",
            "ingresos_periodo": str(ingresos_periodo),
            "ingresos_periodo_anterior": str(ingresos_anterior),
            "crecimiento_ingresos_pct": crecimiento,
            "ticket_promedio": str(ingresos_periodo / pagos_periodo if pagos_periodo else 0),
            "pagos_periodo": pagos_periodo,
            "nuevas_empresas": sum(empresas_por_mes.values()),
            "tasa_activacion_pct": (
                round(empresas_activas / empresas_total * 100, 1) if empresas_total else 0
            ),
            "serie": serie,
            "planes_vigentes": planes,
            "actualizado_en": ahora.isoformat(),
        }

    @staticmethod
    def _plan_dict(p):
        return {
            "nombre": p.nombre,
            "precio_mensual": str(p.precio_mensual),
            "precio_anual": str(p.precio_anual),
            "limite_productos": p.limite_productos,
            "limite_usuarios": p.limite_usuarios,
            "funciones": dict(p.funciones or {}),
            "activo": p.activo,
        }

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.actor, permiso)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)

    def _auditar(self, accion, tipo, id_, datos):
        registrar_auditoria(
            accion=accion,
            modulo="superadministracion",
            usuario_id=self.actor.id,
            empresa_id=None,
            entidad_tipo=tipo,
            entidad_id=id_,
            datos_nuevos=datos,
        )
