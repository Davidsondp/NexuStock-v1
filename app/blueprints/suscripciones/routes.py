from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for
from flask_login import current_user, login_required

from ...extensions import csrf
from ...models import DocumentoFacturacionSaaS, Suscripcion, db
from ...permisos import requerir_permiso
from ...services.planes import (
    CATALOGO_CAPACIDADES,
    capacidades_del_plan,
)
from ...services.conciliacion_pagos import (
    ConciliacionPagoNoDisponible,
    conciliar_antes_de_cancelar,
    consultar_estado_solicitud,
)
from ...services.pagos_webpay import (
    ErrorCheckoutWebpay,
    ErrorProveedorWebpay,
    TokenWebpayInvalido,
    WebpayNoConfigurado,
    cancelar_checkout_webpay,
    confirmar_checkout_webpay,
    iniciar_checkout_webpay,
    obtener_transaccion_webpay,
)
from ...services.pagos_mercadopago import (
    ErrorCheckoutMercadoPago,
    ErrorProveedorMercadoPago,
    FirmaMercadoPagoInvalida,
    MercadoPagoNoConfigurado,
    iniciar_checkout_mercadopago,
    obtener_cliente_mercadopago,
    procesar_webhook_mercadopago,
    verificar_firma_mercadopago,
)
from ...services.suscripciones import (
    ConflictoPago,
    ErrorSuscripcion,
    ServicioSuscripciones,
)
from ...services.pagos_recurrentes import (
    ErrorPagoRecurrente,
    confirmar_mandato_mercadopago,
    confirmar_mandato_oneclick,
    iniciar_mandato,
    procesar_evento_suscripcion_mercadopago,
)

suscripciones_bp = Blueprint("suscripciones", __name__, url_prefix="/api/suscripciones")
webhooks_pago_bp = Blueprint("webhooks_pago", __name__, url_prefix="/webhooks/pagos")


def _limites(plan):
    return {
        "productos": plan.limite_productos,
        "usuarios": plan.limite_usuarios,
        "movimientos_mes": plan.limite_movimientos_mes,
        "sucursales": plan.limite_sucursales,
        "bodegas": plan.limite_bodegas,
    }


def _plan(plan):
    return {
        "id": plan.id,
        "codigo": plan.codigo,
        "nombre": plan.nombre,
        "descripcion": plan.descripcion,
        "precio_mensual": str(plan.precio_mensual),
        "precio_anual": str(plan.precio_anual),
        "moneda": plan.moneda,
        "nivel_comercial": plan.nivel_comercial,
        "soporte": plan.soporte,
        "requiere_cotizacion": plan.codigo in {"empresa", "corporativo"},
        "limites": _limites(plan),
        "funciones": dict(plan.funciones or {}),
        "capacidades": capacidades_del_plan(plan.funciones),
    }


def _solicitud(s):
    ultimo_pago = max(s.pagos, key=lambda pago: pago.id, default=None)
    return {
        "id": s.id,
        "plan_solicitado_id": s.plan_solicitado_id,
        "ciclo": s.ciclo,
        "monto_esperado": str(s.monto_esperado),
        "moneda": s.moneda,
        "estado": s.estado,
        "proveedor_preferido": s.proveedor_preferido,
        "ultimo_pago": (
            {
                "id": ultimo_pago.id,
                "proveedor": ultimo_pago.proveedor,
                "estado": ultimo_pago.estado,
                "referencia": ultimo_pago.referencia_externa,
                "fecha_vencimiento": (
                    ultimo_pago.fecha_vencimiento.isoformat()
                    if ultimo_pago.fecha_vencimiento
                    else None
                ),
            }
            if ultimo_pago
            else None
        ),
    }


def _error(exc, estado=400):
    return (
        jsonify({"codigo": getattr(exc, "codigo", "suscripcion_invalida"), "mensaje": str(exc)}),
        estado,
    )


def _documento(documento):
    return {
        "id": documento.id,
        "numero": documento.numero,
        "tipo": documento.tipo,
        "estado": documento.estado,
        "moneda": documento.moneda,
        "total": str(documento.total),
        "cliente_nombre": documento.cliente_nombre,
        "cliente_identificacion_fiscal": documento.cliente_identificacion_fiscal,
        "cliente_email": documento.cliente_email,
        "concepto": documento.concepto,
        "emitido_en": documento.emitido_en.isoformat(),
    }


@suscripciones_bp.get("")
@login_required
@requerir_permiso("suscripciones.ver")
def resumen():
    servicio = ServicioSuscripciones(current_user)
    suscripcion, solicitudes = servicio.resumen()
    plan_actual = suscripcion.plan

    return jsonify(
        {
            "suscripcion": {
                # Contrato histórico conservado.
                "plan": plan_actual.codigo,
                "estado": suscripcion.estado,
                "ciclo": suscripcion.ciclo,
                "fecha_inicio": suscripcion.fecha_inicio.isoformat(),
                "fecha_fin": (suscripcion.fecha_fin.isoformat() if suscripcion.fecha_fin else None),
                "renovacion_automatica": suscripcion.renovacion_automatica,
                "cancelar_al_fin_periodo": suscripcion.cancelar_al_fin_periodo,
                "metodo_pago_recurrente_estado": (suscripcion.metodo_pago_recurrente_estado),
                "proveedor_cobro": suscripcion.proveedor_cobro,
                "fecha_proximo_cobro": (
                    suscripcion.fecha_proximo_cobro.isoformat()
                    if suscripcion.fecha_proximo_cobro
                    else None
                ),
                "intentos_cobro": suscripcion.intentos_cobro,
                "gracia_hasta": (
                    suscripcion.gracia_hasta.isoformat() if suscripcion.gracia_hasta else None
                ),
                # Contrato empresarial ampliado.
                "plan_nombre": plan_actual.nombre,
                "limites": _limites(plan_actual),
                "funciones": dict(plan_actual.funciones or {}),
                "capacidades": capacidades_del_plan(plan_actual.funciones),
            },
            "catalogo_capacidades": [dict(capacidad) for capacidad in CATALOGO_CAPACIDADES],
            "planes_disponibles": [_plan(plan) for plan in servicio.planes_disponibles()],
            "solicitudes": [_solicitud(solicitud) for solicitud in solicitudes],
        }
    )


@suscripciones_bp.post("/mandato/iniciar")
@login_required
@requerir_permiso("suscripciones.solicitar")
def iniciar_mandato_route():
    try:
        datos = request.get_json(silent=True) or {}
        mandato = iniciar_mandato(
            usuario=current_user,
            proveedor=datos.get("proveedor"),
            base_url=current_app.config.get("BASE_URL") or request.url_root,
            configuracion=current_app.config,
        )
        if mandato.token:
            session["mandato_oneclick_token"] = mandato.token
        return (
            jsonify(
                {
                    "proveedor": mandato.proveedor,
                    "referencia": mandato.referencia,
                    "url_redireccion": mandato.url,
                    "token": mandato.token,
                    "campo_token": "TBK_TOKEN" if mandato.token else None,
                }
            ),
            201,
        )
    except ErrorPagoRecurrente as exc:
        return _error(exc, 503 if "credenciales" in str(exc).lower() else 400)


@webhooks_pago_bp.route("/mandato/webpay/retorno", methods=["GET", "POST"])
@csrf.exempt
def retorno_mandato_webpay():
    token = str(request.values.get("TBK_TOKEN") or "").strip()
    suscripcion = db.session.scalar(
        db.select(Suscripcion).where(
            Suscripcion.referencia_metodo_pago == "pendiente:" + token,
            Suscripcion.metodo_pago_recurrente_estado == "pendiente",
        )
    )
    if not token or not suscripcion:
        return _error(ErrorPagoRecurrente("Inscripción Oneclick no encontrada"), 400)
    try:
        confirmar_mandato_oneclick(
            suscripcion=suscripcion,
            token=token,
            configuracion=current_app.config,
        )
        session.pop("mandato_oneclick_token", None)
        return redirect(url_for("panel.inicio", mandato="activo"))
    except ErrorPagoRecurrente as exc:
        return _error(exc, 400)


@webhooks_pago_bp.get("/mandato/mercadopago/retorno")
def retorno_mandato_mercadopago():
    referencia = str(request.args.get("preapproval_id") or request.args.get("id") or "").strip()
    suscripcion = db.session.scalar(
        db.select(Suscripcion)
        .execution_options(populate_existing=True)
        .where(
            Suscripcion.referencia_metodo_pago == referencia,
            Suscripcion.proveedor_cobro == "mercadopago",
        )
    )
    if not referencia or not suscripcion:
        return _error(ErrorPagoRecurrente("Suscripción de Mercado Pago no encontrada"), 400)
    if suscripcion.metodo_pago_recurrente_estado == "activo":
        return redirect(url_for("panel.inicio", mandato="activo"))

    try:
        confirmar_mandato_mercadopago(
            suscripcion=suscripcion,
            configuracion=current_app.config,
        )
        return redirect(url_for("panel.inicio", mandato="activo"))
    except ErrorPagoRecurrente as exc:
        return _error(exc, 400)


@suscripciones_bp.get("/documentos")
@login_required
@requerir_permiso("suscripciones.ver")
def documentos_facturacion():
    documentos = db.session.scalars(
        db.select(DocumentoFacturacionSaaS)
        .where(DocumentoFacturacionSaaS.empresa_id == current_user.empresa_id)
        .order_by(DocumentoFacturacionSaaS.emitido_en.desc())
        .limit(100)
    )
    return jsonify({"documentos": [_documento(documento) for documento in documentos]})


@suscripciones_bp.post("/cancelacion-programada")
@login_required
@requerir_permiso("suscripciones.solicitar")
def programar_cancelacion():
    try:
        datos = request.get_json(silent=True) or {}
        suscripcion = ServicioSuscripciones(current_user).programar_cancelacion(
            motivo=datos.get("motivo")
        )
        return jsonify(
            {
                "estado": suscripcion.estado,
                "cancelar_al_fin_periodo": suscripcion.cancelar_al_fin_periodo,
                "fecha_fin": suscripcion.fecha_fin.isoformat() if suscripcion.fecha_fin else None,
            }
        )
    except ErrorSuscripcion as exc:
        return _error(exc)


@suscripciones_bp.post("/renovacion/reactivar")
@login_required
@requerir_permiso("suscripciones.solicitar")
def reactivar_renovacion():
    try:
        suscripcion = ServicioSuscripciones(current_user).reactivar_renovacion()
        return jsonify(
            {
                "estado": suscripcion.estado,
                "renovacion_automatica": suscripcion.renovacion_automatica,
                "cancelar_al_fin_periodo": suscripcion.cancelar_al_fin_periodo,
            }
        )
    except ErrorSuscripcion as exc:
        return _error(exc)


@suscripciones_bp.post("/solicitudes")
@login_required
@requerir_permiso("suscripciones.solicitar")
def solicitar():
    try:
        datos = request.get_json(silent=True) or {}
        return (
            jsonify(
                _solicitud(
                    ServicioSuscripciones(current_user).solicitar_cambio(
                        plan_codigo=datos.get("plan_codigo"),
                        ciclo=datos.get("ciclo"),
                        proveedor=datos.get("proveedor"),
                    )
                )
            ),
            201,
        )
    except ErrorSuscripcion as exc:
        return _error(exc, 409 if isinstance(exc, ConflictoPago) else 400)


@suscripciones_bp.post("/solicitudes/<int:solicitud_id>/cancelar")
@login_required
@requerir_permiso("suscripciones.solicitar")
def cancelar(solicitud_id):
    try:
        conciliar_antes_de_cancelar(
            usuario=current_user,
            solicitud_id=solicitud_id,
            configuracion=current_app.config,
        )
        return jsonify(
            _solicitud(ServicioSuscripciones(current_user).cancelar_solicitud(solicitud_id))
        )
    except ErrorSuscripcion as exc:
        if getattr(exc, "codigo", "") == "conciliacion_pago_no_disponible":
            solicitud = ServicioSuscripciones(current_user).marcar_cancelacion_en_revision(
                solicitud_id, motivo=str(exc)
            )
            respuesta = _solicitud(solicitud)
            respuesta.update({"codigo": exc.codigo, "mensaje": str(exc)})
            return jsonify(respuesta), 202
        return _error(exc, 409 if isinstance(exc, ConflictoPago) else 400)


@suscripciones_bp.patch("/solicitudes/<int:solicitud_id>")
@login_required
@requerir_permiso("suscripciones.solicitar")
def cambiar_solicitud(solicitud_id):
    try:
        datos = request.get_json(silent=True) or {}
        solicitud = ServicioSuscripciones(current_user).cambiar_solicitud(
            solicitud_id,
            plan_codigo=datos.get("plan_codigo"),
            ciclo=datos.get("ciclo"),
            proveedor=datos.get("proveedor"),
        )
        return jsonify(_solicitud(solicitud))
    except ErrorSuscripcion as exc:
        return _error(exc, 409 if isinstance(exc, ConflictoPago) else 400)


@suscripciones_bp.post("/solicitudes/<int:solicitud_id>/conciliar")
@login_required
@requerir_permiso("suscripciones.solicitar")
def consultar_estado(solicitud_id):
    try:
        consultar_estado_solicitud(
            usuario=current_user, solicitud_id=solicitud_id, configuracion=current_app.config
        )
        _, solicitudes = ServicioSuscripciones(current_user).resumen()
        solicitud = next((item for item in solicitudes if item.id == solicitud_id), None)
        if not solicitud:
            raise PermissionError("Solicitud no autorizada")
        return jsonify(_solicitud(solicitud))
    except ConciliacionPagoNoDisponible as exc:
        return _error(exc, 202)
    except ErrorSuscripcion as exc:
        return _error(exc, 409 if isinstance(exc, ConflictoPago) else 400)


def _pago_webpay(pago):
    datos = dict(pago.datos_proveedor or {})

    return {
        "id": pago.id,
        "proveedor": pago.proveedor,
        "referencia_externa": pago.referencia_externa,
        "estado": pago.estado,
        "monto": str(pago.monto),
        "moneda": pago.moneda,
        "token": datos.get("token"),
        "url_redireccion": datos.get("url_redireccion"),
    }


def _pago_mercadopago(pago):
    datos = dict(pago.datos_proveedor or {})
    return {
        "id": pago.id,
        "proveedor": pago.proveedor,
        "referencia_externa": pago.referencia_externa,
        "estado": pago.estado,
        "monto": str(pago.monto),
        "moneda": pago.moneda,
        "preferencia_id": datos.get("preferencia_id"),
        "url_redireccion": datos.get("init_point"),
    }


@suscripciones_bp.post("/solicitudes/<int:solicitud_id>" "/checkout/webpay")
@login_required
@requerir_permiso("suscripciones.solicitar")
def iniciar_checkout_webpay_route(
    solicitud_id,
):
    try:
        transaccion = obtener_transaccion_webpay(current_app.config)

        base_url = (current_app.config.get("BASE_URL") or "").rstrip("/")

        return_url = (
            base_url + "/webhooks/pagos/webpay/retorno"
            if base_url
            else url_for(
                "webhooks_pago.retorno_webpay",
                _external=True,
            )
        )

        resultado = iniciar_checkout_webpay(
            usuario=current_user,
            solicitud_id=solicitud_id,
            transaccion=transaccion,
            return_url=return_url,
        )

        return jsonify(_pago_webpay(resultado.pago)), (200 if resultado.reutilizado else 201)

    except WebpayNoConfigurado as exc:
        return _error(exc, 503)

    except ErrorProveedorWebpay as exc:
        return _error(exc, 502)

    except ConflictoPago as exc:
        return _error(exc, 409)

    except ErrorCheckoutWebpay as exc:
        return _error(exc, 400)


@suscripciones_bp.post("/solicitudes/<int:solicitud_id>/checkout/mercadopago")
@login_required
@requerir_permiso("suscripciones.solicitar")
def iniciar_checkout_mercadopago_route(solicitud_id):
    try:
        cliente = obtener_cliente_mercadopago(current_app.config)
        resultado = iniciar_checkout_mercadopago(
            usuario=current_user,
            solicitud_id=solicitud_id,
            cliente=cliente,
            base_url=current_app.config.get("BASE_URL"),
            ambiente=current_app.config.get("MERCADOPAGO_ENV", "production"),
        )
        return jsonify(_pago_mercadopago(resultado.pago)), (200 if resultado.reutilizado else 201)
    except MercadoPagoNoConfigurado as exc:
        return _error(exc, 503)
    except ErrorProveedorMercadoPago as exc:
        return _error(exc, 502)
    except ConflictoPago as exc:
        return _error(exc, 409)
    except ErrorCheckoutMercadoPago as exc:
        return _error(exc, 400)


@webhooks_pago_bp.route(
    "/webpay/retorno",
    methods=["GET", "POST"],
)
@csrf.exempt
def retorno_webpay():
    token = request.values.get("token_ws")
    token_cancelado = request.values.get("TBK_TOKEN")
    orden_cancelada = request.values.get("TBK_ORDEN_COMPRA")
    sesion_cancelada = request.values.get("TBK_ID_SESION")

    try:
        if token_cancelado:
            cancelar_checkout_webpay(
                token=token_cancelado,
                referencia=orden_cancelada,
                sesion=sesion_cancelada,
            )

            return redirect(
                url_for(
                    "panel.inicio",
                    checkout="cancelado",
                )
            )

        if not token:
            raise TokenWebpayInvalido("El token Webpay no es válido")

        transaccion = obtener_transaccion_webpay(current_app.config)

        confirmar_checkout_webpay(
            token=token,
            transaccion=transaccion,
        )

        return redirect(
            url_for(
                "panel.administracion_planes",
                checkout="exito",
            )
        )

    except TokenWebpayInvalido as exc:
        return _error(exc, 400)

    except ConflictoPago as exc:
        return _error(exc, 409)

    except WebpayNoConfigurado as exc:
        return _error(exc, 503)

    except ErrorProveedorWebpay as exc:
        return _error(exc, 502)

    except ErrorCheckoutWebpay as exc:
        return _error(exc, 400)


@webhooks_pago_bp.get("/mercadopago/retorno")
def retorno_mercadopago():
    resultado = str(request.args.get("resultado") or "pendiente").strip().lower()

    if resultado not in {"exito", "error", "pendiente"}:
        resultado = "pendiente"

    if current_user.is_authenticated:
        if current_user.rol == "super_admin":
            destino = url_for("panel_superadministracion.inicio")
        else:
            destino = url_for(
                "panel.inicio",
                checkout=resultado,
                proveedor="mercadopago",
            )
    else:
        destino = url_for(
            "autenticacion.ingresar",
            checkout=resultado,
            proveedor="mercadopago",
        )

    return redirect(destino)


@webhooks_pago_bp.post("/mercadopago")
@csrf.exempt
def webhook_mercadopago():
    datos = request.get_json(silent=True) or {}
    data_id = str(request.args.get("data.id") or (datos.get("data") or {}).get("id") or "").strip()
    tipo_evento = str(datos.get("type") or request.args.get("type") or "payment").strip().lower()
    try:
        verificar_firma_mercadopago(
            secreto=current_app.config.get("MERCADOPAGO_WEBHOOK_SECRET"),
            firma=request.headers.get("X-Signature"),
            request_id=request.headers.get("X-Request-Id"),
            data_id=data_id,
        )
        if tipo_evento.startswith("subscription_"):
            suscripcion, procesado, estado = procesar_evento_suscripcion_mercadopago(
                tipo_evento=tipo_evento,
                referencia=data_id,
                configuracion=current_app.config,
            )

            return jsonify(
                {
                    "recibido": True,
                    "procesado": procesado,
                    "tipo": tipo_evento,
                    "suscripcion_id": (suscripcion.id if suscripcion else None),
                    "estado": estado,
                }
            )

        pago, procesado = procesar_webhook_mercadopago(
            cliente=obtener_cliente_mercadopago(current_app.config),
            pago_proveedor_id=data_id,
        )
        return jsonify(
            {
                "recibido": True,
                "procesado": procesado,
                "pago_id": pago.id,
                "estado": pago.estado,
            }
        )
    except FirmaMercadoPagoInvalida as exc:
        return _error(exc, 401)
    except MercadoPagoNoConfigurado as exc:
        return _error(exc, 503)
    except ConflictoPago as exc:
        return _error(exc, 409)
    except ErrorProveedorMercadoPago as exc:
        return _error(exc, 502)
    except ErrorCheckoutMercadoPago as exc:
        return _error(exc, 400)
    except ErrorPagoRecurrente as exc:
        return _error(exc, 502)
