import hashlib
import hmac
import json
import time
from datetime import timedelta
from decimal import Decimal

import pytest

from app.models import (
    Auditoria,
    DocumentoFacturacionSaaS,
    Empresa,
    Pago,
    PlanSaaS,
    SolicitudCambioPlan,
    Usuario,
    db,
    utcnow,
)
from app.services.pagos_recurrentes import (
    confirmar_mandato_mercadopago,
    confirmar_mandato_oneclick,
    iniciar_mandato,
    procesar_renovaciones,
)
from app.services.planes import CATALOGO_CAPACIDADES
from app.services.suscripciones import (
    ConflictoPago,
    ErrorSuscripcion,
    FirmaWebhookInvalida,
    ProcesadorWebhooksPago,
    ServicioSuscripciones,
)
from tests.test_autenticacion import REGISTRO

SECRETO = "secreto-pruebas-webhook-pagos-123456789"


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        plan = PlanSaaS(
            codigo="profesional",
            nombre="Profesional Pago",
            precio_mensual=19990,
            precio_anual=199900,
            moneda="CLP",
            dias_prueba=0,
            limite_productos=5000,
            limite_usuarios=10,
            limite_movimientos_mes=50000,
            limite_sucursales=3,
            limite_bodegas=3,
            funciones={"analitica": True},
        )
        db.session.add(plan)
        db.session.commit()
        return usuario.id, plan.id


def _flujo(ids, referencia="PAGO-001"):
    servicio = ServicioSuscripciones(db.session.get(Usuario, ids[0]))
    solicitud = servicio.solicitar_cambio(
        plan_codigo="profesional", ciclo="mensual", proveedor="mercadopago"
    )
    pago = servicio.iniciar_pago(
        solicitud.id, proveedor="mercadopago", referencia_externa=referencia
    )
    return solicitud, pago


def _evento(referencia="PAGO-001", estado="pagado", monto="19990.00", moneda="CLP"):
    cuerpo = json.dumps(
        {"referencia_externa": referencia, "estado": estado, "monto": monto, "moneda": moneda},
        separators=(",", ":"),
    ).encode()
    marca = str(int(time.time()))
    firma = hmac.new(SECRETO.encode(), marca.encode() + b"." + cuerpo, hashlib.sha256).hexdigest()
    return cuerpo, marca, firma


class MercadoPagoRecurrenteFalso:
    def __init__(self):
        self.datos = None

    def crear_mandato(self, datos):
        self.datos = datos
        return {"id": "preapproval-1", "init_point": "https://pago.example/autorizar"}

    def obtener_mandato(self, referencia):
        assert referencia == "preapproval-1"
        return {"status": "authorized", "external_reference": self.datos["external_reference"]}

    def buscar_cobros(self, referencia):
        return []


class OneclickFalso:
    def iniciar_inscripcion(self, **datos):
        assert datos["response_url"].startswith("https://")
        return {"token": "tbk-token-1", "url_webpay": "https://webpay.example/inscribir"}

    def finalizar_inscripcion(self, token):
        assert token == "tbk-token-1"
        return {"tbk_user": "tbk-user-tokenizado", "response_code": 0}


def test_mandato_mercadopago_inicia_sin_cobro_y_activa_renovacion(app, client):
    ids = _preparar(app, client)
    falso = MercadoPagoRecurrenteFalso()
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        ServicioSuscripciones(usuario).solicitar_cambio(
            plan_codigo="profesional", ciclo="mensual", proveedor="mercadopago"
        )
        suscripcion = usuario.empresa.suscripcion_actual
        mandato = iniciar_mandato(
            usuario=usuario,
            proveedor="mercadopago",
            base_url="https://nexustock.test",
            configuracion={"MERCADOPAGO_SUSCRIPCIONES_FACTORY": lambda: falso},
        )
        assert mandato.url == "https://pago.example/autorizar"
        assert falso.datos["auto_recurring"]["start_date"].startswith(
            suscripcion.fecha_fin.date().isoformat()
        )
        assert suscripcion.renovacion_automatica is False
        confirmar_mandato_mercadopago(
            suscripcion=suscripcion,
            configuracion={"MERCADOPAGO_SUSCRIPCIONES_FACTORY": lambda: falso},
        )
        assert suscripcion.metodo_pago_recurrente_estado == "activo"
        assert suscripcion.renovacion_automatica is True
        assert suscripcion.fecha_proximo_cobro == suscripcion.fecha_fin


def test_mandato_oneclick_guarda_solo_referencia_tokenizada(app, client):
    ids = _preparar(app, client)
    falso = OneclickFalso()
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        ServicioSuscripciones(usuario).solicitar_cambio(
            plan_codigo="profesional", ciclo="mensual", proveedor="webpay"
        )
        suscripcion = usuario.empresa.suscripcion_actual
        mandato = iniciar_mandato(
            usuario=usuario,
            proveedor="webpay",
            base_url="https://nexustock.test",
            configuracion={"WEBPAY_ONECLICK_FACTORY": lambda: falso},
        )
        assert mandato.token == "tbk-token-1"
        confirmar_mandato_oneclick(
            suscripcion=suscripcion,
            token=mandato.token,
            configuracion={"WEBPAY_ONECLICK_FACTORY": lambda: falso},
        )
        assert suscripcion.referencia_metodo_pago == "tbk-user-tokenizado"
        assert suscripcion.metodo_pago_recurrente_estado == "activo"


def test_rechazo_respeta_fecha_de_reintento_y_mantiene_gracia(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        ServicioSuscripciones(usuario).solicitar_cambio(
            plan_codigo="profesional", ciclo="mensual", proveedor="mercadopago"
        )
        suscripcion = usuario.empresa.suscripcion_actual
        ahora = utcnow()
        suscripcion.proveedor_cobro = "mercadopago"
        suscripcion.referencia_metodo_pago = "preapproval-1"
        suscripcion.metodo_pago_recurrente_estado = "activo"
        suscripcion.renovacion_automatica = True
        suscripcion.fecha_inicio = ahora - timedelta(days=31)
        suscripcion.fecha_fin = ahora - timedelta(minutes=1)
        suscripcion.fecha_proximo_cobro = suscripcion.fecha_fin
        db.session.commit()
        configuracion = {
            "MERCADOPAGO_SUSCRIPCIONES_FACTORY": MercadoPagoRecurrenteFalso,
            "RENOVACION_MAX_REINTENTOS": 3,
            "RENOVACION_GRACIA_DIAS": 7,
        }
        primero = procesar_renovaciones(configuracion=configuracion, ahora=ahora)
        assert primero["rechazadas"] == 1
        assert suscripcion.intentos_cobro == 1
        assert suscripcion.esta_vigente(ahora)
        segundo = procesar_renovaciones(
            configuracion=configuracion, ahora=ahora + timedelta(hours=1)
        )
        assert segundo["procesadas"] == 0
        assert suscripcion.intentos_cobro == 1


def test_solicitud_congela_plan_ciclo_y_precio(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        solicitud, _ = _flujo(ids)
        assert solicitud.ciclo == "mensual" and solicitud.monto_esperado == 19990
        assert solicitud.moneda == "CLP" and solicitud.estado == "pago_en_proceso"


def test_pago_aprobado_durante_cancelacion_en_revision_activa_plan(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        solicitud, pago = _flujo(ids)
        solicitud.estado = "cancelacion_en_revision"
        db.session.commit()
        cuerpo, marca, firma = _evento()
        confirmado, procesado = ProcesadorWebhooksPago(SECRETO).procesar(
            cuerpo, proveedor="mercadopago", marca_tiempo=marca, firma=firma
        )
        assert procesado and confirmado.estado == "pagado"
        assert solicitud.estado == "aprobada"
        assert pago.suscripcion.plan_id == ids[1]


def test_pago_aprobado_despues_de_cancelacion_confirmada_es_incidencia(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        solicitud, pago = _flujo(ids)
        plan_original = pago.suscripcion.plan_id
        solicitud.estado = "cancelada"
        db.session.commit()
        cuerpo, marca, firma = _evento()
        confirmado, procesado = ProcesadorWebhooksPago(SECRETO).procesar(
            cuerpo, proveedor="mercadopago", marca_tiempo=marca, firma=firma
        )
        assert procesado and confirmado.estado == "incidencia"
        assert solicitud.estado == "cancelada"
        assert pago.suscripcion.plan_id == plan_original


def test_solo_una_solicitud_pendiente(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioSuscripciones(db.session.get(Usuario, ids[0]))
        servicio.solicitar_cambio(plan_codigo="profesional", ciclo="mensual", proveedor="webpay")
        with pytest.raises(ErrorSuscripcion):
            servicio.solicitar_cambio(plan_codigo="profesional", ciclo="anual", proveedor="webpay")


def test_solicitud_pendiente_puede_cambiar_plan_ciclo_y_proveedor(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioSuscripciones(db.session.get(Usuario, ids[0]))
        solicitud = servicio.solicitar_cambio(
            plan_codigo="profesional", ciclo="mensual", proveedor="webpay"
        )
        actualizada = servicio.cambiar_solicitud(
            solicitud.id,
            plan_codigo="profesional",
            ciclo="anual",
            proveedor="mercadopago",
        )
        assert actualizada.ciclo == "anual"
        assert actualizada.proveedor_preferido == "mercadopago"
        assert actualizada.monto_esperado == Decimal("199900.00")


def test_referencia_pago_es_idempotente_global(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        _flujo(ids)
        solicitud = db.session.scalar(db.select(SolicitudCambioPlan))
        solicitud.estado = "cancelada"
        db.session.commit()
        servicio = ServicioSuscripciones(db.session.get(Usuario, ids[0]))
        nueva = servicio.solicitar_cambio(
            plan_codigo="profesional", ciclo="anual", proveedor="mercadopago"
        )
        with pytest.raises(ConflictoPago):
            servicio.iniciar_pago(nueva.id, proveedor="mercadopago", referencia_externa="PAGO-001")


def test_webhook_pagado_activa_plan_atomicamente(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        solicitud, pago = _flujo(ids)
        cuerpo, marca, firma = _evento()
        confirmado, procesado = ProcesadorWebhooksPago(SECRETO).procesar(
            cuerpo, proveedor="mercadopago", marca_tiempo=marca, firma=firma
        )
        suscripcion = db.session.get(Usuario, ids[0]).empresa.suscripcion_actual
        assert procesado and confirmado.estado == "pagado"
        assert solicitud.estado == "aprobada" and suscripcion.plan_id == ids[1]
        assert suscripcion.ciclo == "mensual" and suscripcion.estado == "activa"
        documento = db.session.scalar(db.select(DocumentoFacturacionSaaS))
        assert documento.pago_id == pago.id
        assert documento.total == Decimal("19990.00")
        assert documento.numero.startswith("NS-")


def test_documento_automatico_es_idempotente_y_visible_en_api(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        _flujo(ids)
        cuerpo, marca, firma = _evento()
        procesador = ProcesadorWebhooksPago(SECRETO)
        procesador.procesar(cuerpo, proveedor="mercadopago", marca_tiempo=marca, firma=firma)
        procesador.procesar(cuerpo, proveedor="mercadopago", marca_tiempo=marca, firma=firma)
        assert db.session.scalar(db.select(db.func.count(DocumentoFacturacionSaaS.id))) == 1
    respuesta = client.get("/api/suscripciones/documentos")
    assert respuesta.status_code == 200
    documentos = respuesta.get_json()["documentos"]
    assert len(documentos) == 1
    assert documentos[0]["total"] == "19990.00"


def test_repeticion_identica_no_duplica_activacion(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        _flujo(ids)
        cuerpo, marca, firma = _evento()
        procesador = ProcesadorWebhooksPago(SECRETO)
        primero, _ = procesador.procesar(
            cuerpo, proveedor="mercadopago", marca_tiempo=marca, firma=firma
        )
        fecha = primero.fecha_confirmacion
        segundo, procesado = procesador.procesar(
            cuerpo, proveedor="mercadopago", marca_tiempo=marca, firma=firma
        )
        assert not procesado and segundo.id == primero.id and segundo.fecha_confirmacion == fecha


def test_monto_incorrecto_rechaza_sin_cambiar_plan(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        solicitud, pago = _flujo(ids)
        plan_original = pago.suscripcion.plan_id
        cuerpo, marca, firma = _evento(monto="1.00")
        with pytest.raises(ConflictoPago):
            ProcesadorWebhooksPago(SECRETO).procesar(
                cuerpo, proveedor="mercadopago", marca_tiempo=marca, firma=firma
            )
        assert db.session.get(Pago, pago.id).estado == "rechazado"
        assert pago.suscripcion.plan_id == plan_original and solicitud.estado == "pendiente"


def test_firma_invalida_y_webhook_vencido_son_rechazados(app, client):
    _preparar(app, client)
    with app.app_context():
        cuerpo, marca, firma = _evento()
        procesador = ProcesadorWebhooksPago(SECRETO)
        with pytest.raises(FirmaWebhookInvalida):
            procesador.verificar(cuerpo, marca, "incorrecta")
        with pytest.raises(FirmaWebhookInvalida):
            procesador.verificar(cuerpo, marca, firma, ahora=int(marca) + 301)


def test_solicitud_ajena_no_es_accesible(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        otra = Empresa(nombre="Ajena", email="pago-ajena@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        solicitud = SolicitudCambioPlan(
            empresa_id=otra.id,
            plan_solicitado_id=ids[1],
            estado="pendiente",
            ciclo="mensual",
            monto_esperado=19990,
            moneda="CLP",
        )
        db.session.add(solicitud)
        db.session.commit()
        with pytest.raises(PermissionError):
            ServicioSuscripciones(db.session.get(Usuario, ids[0])).cancelar_solicitud(solicitud.id)


def test_no_existe_webhook_generico_capaz_de_activar_planes(app, client):
    ids = _preparar(app, client)
    app.config["WEBHOOK_PAGOS_SECRET"] = SECRETO
    solicitud = client.post(
        "/api/suscripciones/solicitudes",
        json={"plan_codigo": "profesional", "ciclo": "mensual", "proveedor": "webpay"},
    ).get_json()
    cuerpo, marca, firma = _evento(referencia="WP-001")
    respuesta = client.post(
        "/webhooks/pagos/webpay",
        data=cuerpo,
        content_type="application/json",
        headers={"X-NexuStock-Timestamp": marca, "X-NexuStock-Signature": firma},
    )
    assert respuesta.status_code == 404


def test_webhook_sin_secreto_no_arranca(app, client):
    _preparar(app, client)
    app.config["WEBHOOK_PAGOS_SECRET"] = None
    cuerpo, marca, firma = _evento()
    with pytest.raises(RuntimeError):
        ProcesadorWebhooksPago(None)


def test_resumen_expone_detalle_del_plan_actual(
    app,
    client,
):
    _preparar(app, client)

    respuesta = client.get("/api/suscripciones")

    assert respuesta.status_code == 200

    datos = respuesta.get_json()
    suscripcion = datos["suscripcion"]

    # Se conserva el contrato existente.
    assert suscripcion["plan"] == "prueba"
    assert suscripcion["estado"] == "prueba"
    assert suscripcion["ciclo"] == "prueba"

    # Detalle requerido por el panel empresarial.
    assert suscripcion["plan_nombre"] == "Prueba"
    assert suscripcion["limites"] == {
        "productos": 100,
        "usuarios": 2,
        "movimientos_mes": 500,
        "sucursales": 1,
        "bodegas": 1,
        "almacenamiento_mb": None,
    }
    assert suscripcion["funciones"]["productos"] is True


def test_resumen_expone_planes_comerciales_activos(
    app,
    client,
):
    _preparar(app, client)

    with app.app_context():
        basico = PlanSaaS(
            codigo="basico-panel",
            nombre="B\u00e1sico Panel",
            descripcion="Operaci\u00f3n esencial",
            precio_mensual=9990,
            precio_anual=99900,
            moneda="CLP",
            dias_prueba=0,
            limite_productos=500,
            limite_usuarios=2,
            limite_movimientos_mes=5000,
            limite_sucursales=1,
            limite_bodegas=1,
            almacenamiento_mb=2000,
            funciones={
                "productos": True,
                "movimientos": True,
            },
            activo=True,
            orden=2,
        )
        inactivo = PlanSaaS(
            codigo="plan-inactivo",
            nombre="Plan inactivo",
            descripcion="No debe exponerse",
            precio_mensual=1,
            precio_anual=1,
            moneda="CLP",
            dias_prueba=0,
            funciones={},
            activo=False,
            orden=99,
        )

        db.session.add_all(
            [
                basico,
                inactivo,
            ]
        )
        db.session.commit()

    respuesta = client.get("/api/suscripciones")

    assert respuesta.status_code == 200

    planes = respuesta.get_json()["planes_disponibles"]

    codigos = [plan["codigo"] for plan in planes]

    assert "prueba" not in codigos
    assert "plan-inactivo" not in codigos
    assert "basico-panel" not in codigos
    assert set(codigos).issubset({"avanzado", "ultra", "profesional", "empresa"})
    assert "profesional" in codigos

    plan = next(plan for plan in planes if plan["codigo"] == "profesional")
    capacidades = plan["capacidades"]

    assert len(capacidades) == len(CATALOGO_CAPACIDADES)
    assert {capacidad["codigo"] for capacidad in capacidades} == {
        capacidad["codigo"] for capacidad in CATALOGO_CAPACIDADES
    }

    assert plan["requiere_cotizacion"] is False
    assert plan["limites"]["productos"] == 5000
    assert plan["limites"]["usuarios"] == 10


def test_resumen_ordena_planes_comerciales(
    app,
    client,
):
    _preparar(app, client)

    with app.app_context():
        primero = PlanSaaS(
            codigo="primero",
            nombre="Primero",
            precio_mensual=100,
            precio_anual=1000,
            moneda="CLP",
            dias_prueba=0,
            funciones={},
            activo=True,
            orden=1,
        )
        ultimo = PlanSaaS(
            codigo="ultimo",
            nombre="\u00daltimo",
            precio_mensual=300,
            precio_anual=3000,
            moneda="CLP",
            dias_prueba=0,
            funciones={},
            activo=True,
            orden=20,
        )

        db.session.add_all(
            [
                ultimo,
                primero,
            ]
        )
        db.session.commit()

    planes = client.get("/api/suscripciones").get_json()["planes_disponibles"]

    codigos = [plan["codigo"] for plan in planes]

    assert "primero" not in codigos and "ultimo" not in codigos


def test_resumen_expone_catalogo_comercial_completo(
    app,
    client,
):
    _preparar(app, client)

    respuesta = client.get("/api/suscripciones")

    assert respuesta.status_code == 200

    catalogo = respuesta.get_json()["catalogo_capacidades"]

    assert len(catalogo) == len(CATALOGO_CAPACIDADES)

    codigos = {capacidad["codigo"] for capacidad in catalogo}

    assert {
        "productos",
        "inventario",
        "ventas",
        "compras",
        "alertas",
        "analitica",
        "multisucursal",
        "transferencias",
        "api",
        "ia",
    }.issubset(codigos)

    ia = next(capacidad for capacidad in catalogo if capacidad["codigo"] == "ia")

    assert ia["estado"] == "disponible"
    assert ia["grupo"] == "inteligencia"


def test_plan_actual_expone_capacidades_comerciales(
    app,
    client,
):
    _preparar(app, client)

    suscripcion = client.get("/api/suscripciones").get_json()["suscripcion"]

    capacidades = suscripcion["capacidades"]

    assert len(capacidades) == len(CATALOGO_CAPACIDADES)

    por_codigo = {capacidad["codigo"]: capacidad for capacidad in capacidades}

    assert por_codigo["productos"]["incluida"] is True
    assert por_codigo["ia"]["incluida"] is False
    assert por_codigo["ia"]["estado"] == "disponible"


def test_planes_disponibles_exponen_matriz_completa(
    app,
    client,
):
    _preparar(app, client)

    planes = client.get("/api/suscripciones").get_json()["planes_disponibles"]

    profesional = next(plan for plan in planes if plan["codigo"] == "profesional")

    capacidades = profesional["capacidades"]

    assert len(capacidades) == len(CATALOGO_CAPACIDADES)

    por_codigo = {capacidad["codigo"]: capacidad for capacidad in capacidades}

    assert por_codigo["analitica"]["incluida"] is True
    assert por_codigo["api"]["incluida"] is False
    assert por_codigo["ia"]["incluida"] is False
