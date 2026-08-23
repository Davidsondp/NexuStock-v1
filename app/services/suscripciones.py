"""Solicitudes, pagos idempotentes y activación de suscripciones."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import hmac
import json
import time

from sqlalchemy.exc import IntegrityError

from ..catalogo_planes import PLANES_AUTOSERVICIO, PLANES_PUBLICOS
from ..models import (
    DocumentoFacturacionSaaS,
    Empresa,
    Pago,
    PlanSaaS,
    SolicitudCambioPlan,
    Suscripcion,
    db,
    utcnow,
)
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria

DOS = Decimal("0.01")
PROVEEDORES = frozenset({"mercadopago", "webpay"})
ESTADOS_PROVEEDOR = {"pagado", "rechazado", "cancelado", "pendiente"}
ESTADOS_SOLICITUD_ABIERTA = {
    "pendiente",
    "pago_en_proceso",
    "cancelacion_en_revision",
}
ESTADOS_PAGO_ACTIVO = {"iniciado", "procesando", "incidencia"}


class ErrorSuscripcion(ValueError):
    codigo = "suscripcion_invalida"


class FirmaWebhookInvalida(ErrorSuscripcion):
    codigo = "firma_webhook_invalida"


class ConflictoPago(ErrorSuscripcion):
    codigo = "conflicto_pago"


class ServicioSuscripciones:
    def __init__(self, usuario):
        self.usuario = usuario
        if not usuario.empresa_id or usuario.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def resumen(self):
        self._exigir("suscripciones.ver")
        suscripcion = suscripcion_facturable(self.usuario.empresa_id)
        if not suscripcion:
            raise ErrorSuscripcion("La empresa no tiene una suscripción base para renovar")
        solicitudes = list(
            db.session.scalars(
                db.select(SolicitudCambioPlan)
                .where(SolicitudCambioPlan.empresa_id == self.usuario.empresa_id)
                .order_by(SolicitudCambioPlan.creado_en.desc())
                .limit(20)
            )
        )
        return suscripcion, solicitudes

    def planes_disponibles(self):
        self._exigir("suscripciones.ver")

        consulta = (
            db.select(PlanSaaS)
            .where(
                PlanSaaS.activo.is_(True),
                PlanSaaS.codigo.in_(PLANES_PUBLICOS),
            )
            .order_by(
                PlanSaaS.orden,
                PlanSaaS.id,
            )
        )

        return list(db.session.scalars(consulta))

    def solicitar_cambio(self, *, plan_codigo, ciclo, proveedor=None):
        self._exigir("suscripciones.solicitar")
        ciclo = (ciclo or "").lower()
        if ciclo not in {"mensual", "anual"}:
            raise ErrorSuscripcion("El ciclo debe ser mensual o anual")
        plan = db.session.scalar(
            db.select(PlanSaaS).where(
                PlanSaaS.codigo == (plan_codigo or "").lower(), PlanSaaS.activo.is_(True)
            )
        )
        if not plan:
            raise ErrorSuscripcion("Plan comercial no disponible")
        if plan.codigo in {"empresa", "corporativo"}:
            raise ErrorSuscripcion("El plan Empresarial requiere una cotización y contrato")
        if plan.codigo not in PLANES_AUTOSERVICIO:
            raise ErrorSuscripcion("Plan comercial no disponible")
        proveedor = (proveedor or "").lower()
        monto = Decimal(plan.precio_mensual if ciclo == "mensual" else plan.precio_anual).quantize(
            DOS
        )
        if monto > 0 and proveedor not in PROVEEDORES:
            raise ErrorSuscripcion("Proveedor de pago no admitido")
        if monto == 0:
            proveedor = "interno"
        actual = self.usuario.empresa.suscripcion_actual
        if actual and actual.plan_id == plan.id and actual.ciclo == ciclo:
            raise ErrorSuscripcion("La empresa ya utiliza ese plan y ciclo")
        pendiente = db.session.scalar(
            db.select(SolicitudCambioPlan).where(
                SolicitudCambioPlan.empresa_id == self.usuario.empresa_id,
                SolicitudCambioPlan.estado.in_(ESTADOS_SOLICITUD_ABIERTA),
            )
        )
        if pendiente:
            raise ErrorSuscripcion("Ya existe una solicitud de cambio pendiente")
        try:
            solicitud = SolicitudCambioPlan(
                empresa_id=self.usuario.empresa_id,
                plan_solicitado_id=plan.id,
                solicitada_por_id=self.usuario.id,
                estado="aprobada" if monto == 0 else "pendiente",
                ciclo=ciclo,
                monto_esperado=monto,
                moneda=plan.moneda,
                proveedor_preferido=proveedor,
            )
            db.session.add(solicitud)
            db.session.flush()
            if monto == 0:
                ahora = utcnow()
                suscripcion = suscripcion_facturable(self.usuario.empresa_id)
                suscripcion.plan_id = plan.id
                suscripcion.estado = "activa"
                suscripcion.ciclo = ciclo
                suscripcion.fecha_inicio = ahora
                suscripcion.fecha_fin = None
                suscripcion.periodo_actual_inicio = ahora
                suscripcion.periodo_actual_fin = None
                suscripcion.gracia_hasta = None
                suscripcion.renovacion_automatica = False
                suscripcion.cancelar_al_fin_periodo = False
                suscripcion.proveedor_cobro = "interno"
                solicitud.revisada_en = ahora
            self._auditar(
                "suscripcion.solicitada",
                "SolicitudCambioPlan",
                solicitud.id,
                {"plan": plan.codigo, "ciclo": ciclo, "monto": str(monto)},
            )
            db.session.commit()
            return solicitud
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorSuscripcion("Ya existe una solicitud pendiente") from exc

    def cancelar_solicitud(self, solicitud_id):
        self._exigir("suscripciones.solicitar")
        solicitud = self._solicitud(solicitud_id, bloquear=True)
        if solicitud.estado not in ESTADOS_SOLICITUD_ABIERTA:
            raise ErrorSuscripcion("La solicitud ya no admite cancelación")
        if db.session.scalar(
            db.select(
                db.exists().where(
                    Pago.solicitud_id == solicitud.id,
                    Pago.estado.in_(ESTADOS_PAGO_ACTIVO | {"pagado"}),
                )
            )
        ):
            raise ErrorSuscripcion("La solicitud tiene un pago en procesamiento o confirmado")
        solicitud.estado = "cancelada"
        solicitud.revisada_en = utcnow()
        self._auditar("suscripcion.cancelada", "SolicitudCambioPlan", solicitud.id, None)
        db.session.commit()
        return solicitud

    def cambiar_solicitud(self, solicitud_id, *, plan_codigo, ciclo, proveedor):
        """Cambia una solicitud sólo cuando ningún cobro puede seguir activo."""
        self._exigir("suscripciones.solicitar")
        solicitud = self._solicitud(solicitud_id, bloquear=True)
        if solicitud.estado != "pendiente":
            raise ConflictoPago("No puedes cambiar una solicitud con un pago en proceso")
        if db.session.scalar(
            db.select(
                db.exists().where(
                    Pago.solicitud_id == solicitud.id,
                    Pago.estado.in_(ESTADOS_PAGO_ACTIVO | {"pagado"}),
                )
            )
        ):
            raise ConflictoPago("Existe un pago que debe conciliarse antes de cambiar el plan")
        ciclo = str(ciclo or "").lower()
        proveedor = str(proveedor or "").lower()
        if ciclo not in {"mensual", "anual"} or proveedor not in PROVEEDORES:
            raise ErrorSuscripcion("Ciclo o proveedor no admitido")
        plan = db.session.scalar(
            db.select(PlanSaaS).where(
                PlanSaaS.codigo == str(plan_codigo or "").lower(),
                PlanSaaS.activo.is_(True),
                PlanSaaS.codigo.in_(PLANES_AUTOSERVICIO),
            )
        )
        if not plan:
            raise ErrorSuscripcion("Plan comercial no disponible")
        if plan.codigo in {"empresa", "corporativo"}:
            raise ErrorSuscripcion("El plan Empresarial requiere una cotización y contrato")
        monto = Decimal(plan.precio_mensual if ciclo == "mensual" else plan.precio_anual).quantize(
            DOS
        )
        solicitud.plan_solicitado_id = plan.id
        solicitud.ciclo = ciclo
        solicitud.monto_esperado = monto
        solicitud.moneda = plan.moneda
        solicitud.proveedor_preferido = proveedor
        self._auditar(
            "suscripcion.solicitud_actualizada",
            "SolicitudCambioPlan",
            solicitud.id,
            {"plan": plan.codigo, "ciclo": ciclo, "proveedor": proveedor, "monto": str(monto)},
        )
        db.session.commit()
        return solicitud

    def marcar_cancelacion_en_revision(self, solicitud_id, *, motivo):
        """Libera la navegación sin afirmar que el proveedor canceló el cobro."""
        self._exigir("suscripciones.solicitar")
        solicitud = self._solicitud(solicitud_id, bloquear=True)
        if solicitud.estado not in ESTADOS_SOLICITUD_ABIERTA:
            return solicitud
        solicitud.estado = "cancelacion_en_revision"
        solicitud.observacion = str(motivo or "Conciliación pendiente")[:1000]
        self._auditar(
            "suscripcion.cancelacion_en_revision",
            "SolicitudCambioPlan",
            solicitud.id,
            {"motivo": solicitud.observacion},
        )
        db.session.commit()
        return solicitud

    def programar_cancelacion(self, *, motivo=None):
        """Detiene la renovación; conserva acceso hasta terminar el período pagado."""
        self._exigir("suscripciones.solicitar")
        suscripcion = suscripcion_facturable(self.usuario.empresa_id)
        if not suscripcion or suscripcion.estado not in {"prueba", "activa"}:
            raise ErrorSuscripcion("No existe una suscripción vigente")
        suscripcion.programar_cancelacion(motivo)
        self._auditar(
            "suscripcion.cancelacion_programada",
            "Suscripcion",
            suscripcion.id,
            {"fecha_fin": suscripcion.fecha_fin.isoformat() if suscripcion.fecha_fin else None},
        )
        db.session.commit()
        return suscripcion

    def reactivar_renovacion(self):
        self._exigir("suscripciones.solicitar")
        suscripcion = suscripcion_facturable(self.usuario.empresa_id)
        if not suscripcion or suscripcion.estado not in {"prueba", "activa"}:
            raise ErrorSuscripcion("No existe una suscripción vigente")
        if suscripcion.metodo_pago_recurrente_estado != "activo":
            raise ErrorSuscripcion(
                "Debes verificar un método de pago recurrente antes de reactivar"
            )
        suscripcion.reactivar_renovacion()
        self._auditar("suscripcion.renovacion_reactivada", "Suscripcion", suscripcion.id, None)
        db.session.commit()
        return suscripcion

    @staticmethod
    def confirmar_metodo_recurrente(*, empresa_id, proveedor, referencia):
        """Activa renovación sólo tras confirmación tokenizada del proveedor."""
        proveedor = str(proveedor or "").lower()
        referencia = str(referencia or "").strip()
        if proveedor not in PROVEEDORES or not referencia or len(referencia) > 180:
            raise ErrorSuscripcion("Método de pago recurrente inválido")
        suscripcion = db.session.scalar(
            db.select(Suscripcion)
            .where(Suscripcion.empresa_id == empresa_id)
            .order_by(Suscripcion.fecha_inicio.desc(), Suscripcion.id.desc())
            .limit(1)
            .with_for_update()
        )
        if not suscripcion or suscripcion.estado not in {"prueba", "activa"}:
            raise ErrorSuscripcion("Suscripción no disponible")
        suscripcion.proveedor_cobro = proveedor
        suscripcion.referencia_metodo_pago = referencia
        suscripcion.metodo_pago_recurrente_estado = "activo"
        suscripcion.renovacion_automatica = suscripcion.metodo_pago_recurrente_estado == "activo"
        if suscripcion.estado == "prueba" and suscripcion.periodo_actual_inicio is None:
            ahora = utcnow()
            dias_prueba = int(suscripcion.plan.dias_prueba or 30)
            suscripcion.fecha_inicio = ahora
            suscripcion.fecha_fin = ahora + timedelta(days=dias_prueba)
            suscripcion.periodo_actual_inicio = ahora
            suscripcion.periodo_actual_fin = suscripcion.fecha_fin
            suscripcion.fecha_proximo_cobro = suscripcion.fecha_fin
        registrar_auditoria(
            accion="suscripcion.metodo_recurrente_activado",
            modulo="suscripciones",
            empresa_id=empresa_id,
            entidad_tipo="Suscripcion",
            entidad_id=suscripcion.id,
            datos_nuevos={"proveedor": proveedor},
        )
        db.session.commit()
        return suscripcion

    def iniciar_pago(self, solicitud_id, *, proveedor, referencia_externa):
        self._exigir("suscripciones.solicitar")
        proveedor = (proveedor or "").lower()
        referencia = (referencia_externa or "").strip()
        if proveedor not in PROVEEDORES:
            raise ErrorSuscripcion("Proveedor de pago no admitido")
        if not referencia or len(referencia) > 150:
            raise ErrorSuscripcion("Referencia externa inválida")
        solicitud = self._solicitud(solicitud_id, bloquear=True)
        if solicitud.monto_esperado == 0:
            raise ErrorSuscripcion("El plan gratuito no requiere checkout")
        if solicitud.estado not in {"pendiente", "pago_en_proceso"}:
            raise ErrorSuscripcion("La solicitud no está pendiente")
        activo = db.session.scalar(
            db.select(Pago.id).where(
                Pago.solicitud_id == solicitud.id,
                Pago.estado.in_(ESTADOS_PAGO_ACTIVO | {"pagado"}),
            )
        )
        if activo:
            raise ConflictoPago("La solicitud ya tiene un pago activo")
        suscripcion = suscripcion_facturable(self.usuario.empresa_id)
        if not suscripcion:
            raise ErrorSuscripcion("La empresa no tiene una suscripción base para renovar")
        try:
            pago = Pago(
                empresa_id=self.usuario.empresa_id,
                suscripcion_id=suscripcion.id,
                solicitud_id=solicitud.id,
                plan_solicitado_id=solicitud.plan_solicitado_id,
                ciclo=solicitud.ciclo,
                proveedor=proveedor,
                referencia_externa=referencia,
                estado="iniciado",
                monto=solicitud.monto_esperado,
                moneda=solicitud.moneda,
                datos_proveedor={},
            )
            db.session.add(pago)
            db.session.flush()
            solicitud.estado = "pago_en_proceso"
            self._auditar(
                "pago.iniciado", "Pago", pago.id, {"proveedor": proveedor, "referencia": referencia}
            )
            db.session.commit()
            return pago
        except IntegrityError as exc:
            db.session.rollback()
            raise ConflictoPago("La referencia de pago ya fue registrada") from exc

    def _solicitud(self, solicitud_id, bloquear=False):
        q = db.select(SolicitudCambioPlan).where(
            SolicitudCambioPlan.id == solicitud_id,
            SolicitudCambioPlan.empresa_id == self.usuario.empresa_id,
        )
        solicitud = db.session.scalar(q.with_for_update() if bloquear else q)
        if not solicitud:
            raise PermissionError("Solicitud no autorizada")
        return solicitud

    def _exigir(self, permiso):
        d = evaluar_permiso(self.usuario, permiso, empresa_id=self.usuario.empresa_id)
        if not d.permitido:
            raise PermissionError(d.mensaje)

    def _auditar(self, accion, tipo, id_, datos):
        registrar_auditoria(
            accion=accion,
            modulo="suscripciones",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo=tipo,
            entidad_id=id_,
            datos_nuevos=datos,
        )


class ProcesadorWebhooksPago:
    TOLERANCIA_SEGUNDOS = 300

    def __init__(self, secreto):
        if not secreto or len(secreto) < 32:
            raise RuntimeError("Secreto de webhook de pagos no configurado")
        self.secreto = secreto.encode()

    def verificar(self, cuerpo: bytes, marca_tiempo: str, firma: str, *, ahora=None):
        try:
            instante = int(marca_tiempo)
        except (TypeError, ValueError) as exc:
            raise FirmaWebhookInvalida("Marca de tiempo inválida") from exc
        ahora = int(ahora if ahora is not None else time.time())
        if abs(ahora - instante) > self.TOLERANCIA_SEGUNDOS:
            raise FirmaWebhookInvalida("Webhook vencido")
        esperada = hmac.new(
            self.secreto, marca_tiempo.encode() + b"." + cuerpo, hashlib.sha256
        ).hexdigest()
        recibida = (firma or "").removeprefix("sha256=")
        if not hmac.compare_digest(esperada, recibida):
            raise FirmaWebhookInvalida("Firma de webhook inválida")

    def procesar(self, cuerpo: bytes, *, proveedor, marca_tiempo, firma):
        self.verificar(cuerpo, marca_tiempo, firma)
        proveedor = (proveedor or "").lower()
        if proveedor not in PROVEEDORES:
            raise ErrorSuscripcion("Proveedor de pago no admitido")
        try:
            datos = json.loads(cuerpo)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ErrorSuscripcion("JSON de webhook inválido") from exc
        referencia = str(datos.get("referencia_externa", "")).strip()
        estado = str(datos.get("estado", "")).lower()
        try:
            monto = Decimal(str(datos.get("monto"))).quantize(DOS, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError) as exc:
            raise ErrorSuscripcion("Monto inválido") from exc
        moneda = str(datos.get("moneda", "")).upper()
        if not referencia or estado not in ESTADOS_PROVEEDOR:
            raise ErrorSuscripcion("Evento de pago inválido")
        pago = db.session.scalar(
            db.select(Pago)
            .where(Pago.proveedor == proveedor, Pago.referencia_externa == referencia)
            .with_for_update()
        )
        if not pago:
            raise ErrorSuscripcion("Pago no encontrado")
        if pago.estado == "pagado":
            if estado == "pagado" and monto == Decimal(pago.monto) and moneda == pago.moneda:
                return pago, False
            raise ConflictoPago("El pago ya fue confirmado con otros datos")
        if monto != Decimal(pago.monto) or moneda != pago.moneda:
            pago.estado = "rechazado"
            pago.datos_proveedor = {"motivo": "monto_o_moneda_no_coincide"}
            solicitud = db.session.get(SolicitudCambioPlan, pago.solicitud_id)
            if solicitud and solicitud.estado == "pago_en_proceso":
                solicitud.estado = "pendiente"
            db.session.commit()
            raise ConflictoPago("El monto o la moneda no coincide con la solicitud")
        try:
            pago.datos_proveedor = {"estado_recibido": estado}
            if estado == "pendiente":
                pago.estado = "procesando"
            elif estado == "rechazado":
                pago.estado = "rechazado"
                solicitud = db.session.get(SolicitudCambioPlan, pago.solicitud_id)
                if solicitud and solicitud.estado == "pago_en_proceso":
                    solicitud.estado = "pendiente"
            elif estado == "cancelado":
                pago.estado = "cancelado"
                solicitud = db.session.get(SolicitudCambioPlan, pago.solicitud_id)
                if solicitud and solicitud.estado == "pago_en_proceso":
                    solicitud.estado = "pendiente"
            else:
                self._confirmar(pago)
            registrar_auditoria(
                accion=f"pago.{pago.estado}",
                modulo="suscripciones",
                empresa_id=pago.empresa_id,
                entidad_tipo="Pago",
                entidad_id=pago.id,
                datos_nuevos={
                    "proveedor": proveedor,
                    "referencia": referencia,
                    "estado": pago.estado,
                },
            )
            db.session.commit()
            return pago, True
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def _confirmar(pago):
        solicitud = db.session.scalar(
            db.select(SolicitudCambioPlan)
            .where(
                SolicitudCambioPlan.id == pago.solicitud_id,
                SolicitudCambioPlan.empresa_id == pago.empresa_id,
            )
            .with_for_update()
        )
        suscripcion = db.session.scalar(
            db.select(Suscripcion)
            .where(Suscripcion.id == pago.suscripcion_id, Suscripcion.empresa_id == pago.empresa_id)
            .with_for_update()
        )
        if not solicitud or not suscripcion:
            raise ConflictoPago("Solicitud o suscripción no disponible")
        if solicitud.estado == "cancelada":
            pago.estado = "incidencia"
            pago.fecha_confirmacion = utcnow()
            pago.datos_proveedor = {
                **(pago.datos_proveedor or {}),
                "motivo_incidencia": "pago_aprobado_despues_de_cancelacion_confirmada",
            }
            registrar_auditoria(
                accion="pago.aprobado_tardio_incidencia",
                modulo="suscripciones",
                empresa_id=pago.empresa_id,
                entidad_tipo="Pago",
                entidad_id=pago.id,
                datos_nuevos={"solicitud_id": solicitud.id},
            )
            return
        if pago.estado == "cancelado" and (pago.datos_proveedor or {}).get(
            "cancelacion_confirmada_proveedor"
        ):
            pago.estado = "incidencia"
            pago.fecha_confirmacion = utcnow()
            pago.datos_proveedor = {
                **(pago.datos_proveedor or {}),
                "motivo_incidencia": "aprobacion_posterior_a_cancelacion_confirmada",
            }
            registrar_auditoria(
                accion="pago.aprobado_tras_cancelacion_proveedor",
                modulo="suscripciones",
                empresa_id=pago.empresa_id,
                entidad_tipo="Pago",
                entidad_id=pago.id,
                datos_nuevos={"solicitud_id": solicitud.id},
            )
            return
        if pago.plan_solicitado_id != solicitud.plan_solicitado_id or pago.ciclo != solicitud.ciclo:
            pago.estado = "incidencia"
            pago.fecha_confirmacion = utcnow()
            pago.datos_proveedor = {
                **(pago.datos_proveedor or {}),
                "motivo_incidencia": "pago_no_coincide_con_solicitud_actual",
            }
            registrar_auditoria(
                accion="pago.plan_inconsistente_incidencia",
                modulo="suscripciones",
                empresa_id=pago.empresa_id,
                entidad_tipo="Pago",
                entidad_id=pago.id,
                datos_nuevos={"solicitud_id": solicitud.id},
            )
            return
        if solicitud.estado not in ESTADOS_SOLICITUD_ABIERTA:
            raise ConflictoPago("La solicitud ya fue resuelta")
        ahora = utcnow()
        duracion = timedelta(days=30 if solicitud.ciclo == "mensual" else 365)
        suscripcion.plan_id = pago.plan_solicitado_id
        suscripcion.estado = "activa"
        suscripcion.ciclo = pago.ciclo
        suscripcion.fecha_inicio = ahora
        suscripcion.fecha_fin = ahora + duracion
        suscripcion.periodo_actual_inicio = ahora
        suscripcion.periodo_actual_fin = ahora + duracion
        suscripcion.gracia_hasta = ahora + duracion + timedelta(days=7)
        suscripcion.renovacion_automatica = suscripcion.metodo_pago_recurrente_estado == "activo"
        suscripcion.cancelar_al_fin_periodo = False
        suscripcion.proveedor_cobro = pago.proveedor
        suscripcion.cancelada_en = None
        suscripcion.motivo_cancelacion = None
        solicitud.estado = "aprobada"
        solicitud.revisada_en = ahora
        pago.estado = "pagado"
        pago.fecha_pago = ahora
        pago.fecha_confirmacion = ahora
        ProcesadorWebhooksPago._emitir_documento_automatico(pago, suscripcion)

    @staticmethod
    def _emitir_documento_automatico(pago, suscripcion):
        """Emite una factura/recibo comercial una sola vez por pago."""
        existente = db.session.scalar(
            db.select(DocumentoFacturacionSaaS).where(DocumentoFacturacionSaaS.pago_id == pago.id)
        )
        if existente:
            return existente
        empresa = db.session.get(Empresa, pago.empresa_id)
        plan = db.session.get(PlanSaaS, pago.plan_solicitado_id)
        documento = DocumentoFacturacionSaaS(
            empresa_id=pago.empresa_id,
            pago_id=pago.id,
            numero=f"NS-{utcnow():%Y}-{int(pago.id):010d}",
            tipo="factura" if empresa.identificacion_fiscal else "recibo",
            estado="emitido",
            moneda=pago.moneda,
            total=pago.monto,
            cliente_nombre=empresa.nombre,
            cliente_identificacion_fiscal=empresa.identificacion_fiscal,
            cliente_email=empresa.email,
            concepto=f"Suscripción NexuStock {plan.nombre} - ciclo {pago.ciclo}",
            datos={
                "proveedor": pago.proveedor,
                "referencia_pago": pago.referencia_externa,
                "suscripcion_id": suscripcion.id,
            },
        )
        db.session.add(documento)
        db.session.flush()
        registrar_auditoria(
            accion="facturacion.documento_emitido",
            modulo="suscripciones",
            empresa_id=pago.empresa_id,
            entidad_tipo="DocumentoFacturacionSaaS",
            entidad_id=documento.id,
            datos_nuevos={"numero": documento.numero, "tipo": documento.tipo},
        )
        return documento

    @staticmethod
    def suspender_por_reembolso(pago):
        posterior = db.session.scalar(
            db.select(
                db.exists().where(
                    Pago.suscripcion_id == pago.suscripcion_id,
                    Pago.estado == "pagado",
                    Pago.id != pago.id,
                    Pago.fecha_confirmacion > pago.fecha_confirmacion,
                )
            )
        )
        if posterior:
            return False
        suscripcion = db.session.scalar(
            db.select(Suscripcion)
            .where(
                Suscripcion.id == pago.suscripcion_id,
                Suscripcion.empresa_id == pago.empresa_id,
            )
            .with_for_update()
        )
        if suscripcion and suscripcion.estado in {"activa", "prueba"}:
            suscripcion.estado = "suspendida"
            suscripcion.fecha_fin = utcnow()
            suscripcion.motivo_cancelacion = "Pago reembolsado o contracargado"
            return True
        return False


def suscripcion_facturable(empresa_id):
    return db.session.scalar(
        db.select(Suscripcion)
        .where(Suscripcion.empresa_id == empresa_id)
        .order_by(Suscripcion.fecha_inicio.desc(), Suscripcion.id.desc())
        .limit(1)
    )
