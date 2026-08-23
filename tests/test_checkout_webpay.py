from decimal import Decimal

from app.models import (
    Pago,
    PlanSaaS,
    SolicitudCambioPlan,
    Suscripcion,
    db,
)
from tests.test_suscripciones import _preparar


class TransaccionWebpayFalsa:
    def __init__(self):
        self.creaciones = []
        self.estado = "INITIALIZED"
        self.respuesta_estado = None

    def create(
        self,
        buy_order,
        session_id,
        amount,
        return_url,
    ):
        self.creaciones.append(
            {
                "buy_order": buy_order,
                "session_id": session_id,
                "amount": amount,
                "return_url": return_url,
            }
        )

        return {
            "token": "TOKEN-WEBPAY-PRUEBA",
            "url": ("https://webpay3gint.transbank.cl/" "webpayserver/initTransaction"),
        }

    def status(self, _token):
        return self.respuesta_estado or {"status": self.estado}


class TransaccionWebpaySinRespuesta(TransaccionWebpayFalsa):
    def create(self, *args, **kwargs):
        raise TimeoutError("sin respuesta")


def preparar_solicitud(app, client, proveedor="webpay"):
    _preparar(app, client)

    respuesta = client.post(
        "/api/suscripciones/solicitudes",
        json={
            "plan_codigo": "profesional",
            "ciclo": "mensual",
            "proveedor": proveedor,
        },
    )

    assert respuesta.status_code == 201

    return respuesta.get_json()


def test_checkout_webpay_genera_referencia_servidor(
    app,
    client,
):
    solicitud = preparar_solicitud(
        app,
        client,
    )
    transaccion = TransaccionWebpayFalsa()

    app.config["WEBPAY_TRANSACCION_FACTORY"] = lambda: transaccion

    respuesta = client.post(
        ("/api/suscripciones/solicitudes/" f"{solicitud['id']}" "/checkout/webpay"),
        json={
            "referencia_externa": ("REFERENCIA-MANIPULADA"),
            "monto": "1.00",
            "moneda": "USD",
        },
    )

    assert respuesta.status_code == 201

    datos = respuesta.get_json()

    assert datos["proveedor"] == "webpay"
    assert datos["estado"] == "procesando"
    assert datos["referencia_externa"] != "REFERENCIA-MANIPULADA"
    assert datos["referencia_externa"].startswith("NS-")
    assert datos["token"] == "TOKEN-WEBPAY-PRUEBA"
    assert datos["url_redireccion"].startswith("https://webpay3gint.transbank.cl/")

    assert len(transaccion.creaciones) == 1

    creacion = transaccion.creaciones[0]

    assert creacion["buy_order"] == datos["referencia_externa"]
    assert creacion["amount"] == Decimal(solicitud["monto_esperado"])
    assert "/pagos/webpay/retorno" in creacion["return_url"]

    with app.app_context():
        pago = db.session.get(
            Pago,
            datos["id"],
        )

        assert pago is not None
        assert pago.referencia_externa == datos["referencia_externa"]
        assert pago.estado == "procesando"
        assert Decimal(pago.monto) == Decimal(solicitud["monto_esperado"])
        assert pago.moneda == "CLP"
        assert pago.datos_proveedor["token"] == "TOKEN-WEBPAY-PRUEBA"
        assert pago.datos_proveedor["url_redireccion"] == datos["url_redireccion"]
        assert pago.fecha_vencimiento is not None
        assert pago.token_proveedor == "TOKEN-WEBPAY-PRUEBA"


def test_checkout_webpay_reutiliza_pago_en_proceso(
    app,
    client,
):
    solicitud = preparar_solicitud(
        app,
        client,
    )
    transaccion = TransaccionWebpayFalsa()

    app.config["WEBPAY_TRANSACCION_FACTORY"] = lambda: transaccion

    ruta = "/api/suscripciones/solicitudes/" f"{solicitud['id']}" "/checkout/webpay"

    primera = client.post(
        ruta,
        json={},
    )
    segunda = client.post(
        ruta,
        json={},
    )

    assert primera.status_code == 201
    assert segunda.status_code == 200

    primer_pago = primera.get_json()
    segundo_pago = segunda.get_json()

    assert segundo_pago["id"] == primer_pago["id"]
    assert segundo_pago["token"] == primer_pago["token"]
    assert segundo_pago["url_redireccion"] == primer_pago["url_redireccion"]
    assert len(transaccion.creaciones) == 1


def test_webpay_sin_respuesta_conserva_incidencia_y_bloquea_otro_cobro(app, client):
    solicitud = preparar_solicitud(app, client)
    app.config["WEBPAY_TRANSACCION_FACTORY"] = TransaccionWebpaySinRespuesta
    ruta = f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/webpay"
    primera = client.post(ruta, json={})
    segunda = client.post(ruta, json={})
    assert primera.status_code == 502
    assert segunda.status_code == 400
    with app.app_context():
        pagos = list(db.session.scalars(db.select(Pago)))
        solicitud_db = db.session.get(SolicitudCambioPlan, solicitud["id"])
        assert len(pagos) == 1
        assert pagos[0].estado == "incidencia"
        assert solicitud_db.estado == "cancelacion_en_revision"

    with app.app_context():
        pagos = list(
            db.session.scalars(db.select(Pago).where(Pago.solicitud_id == solicitud["id"]))
        )

        assert len(pagos) == 1


def test_cancelacion_concilia_webpay_fallido_y_libera_solicitud(app, client):
    solicitud = preparar_solicitud(app, client)
    transaccion = TransaccionWebpayFalsa()
    app.config["WEBPAY_TRANSACCION_FACTORY"] = lambda: transaccion
    inicio = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/webpay",
        json={},
    )
    assert inicio.status_code == 201

    transaccion.estado = "FAILED"
    respuesta = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/cancelar",
        json={},
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "cancelada"
    with app.app_context():
        pago = db.session.get(Pago, inicio.get_json()["id"])
        assert pago.estado == "rechazado"


def test_cancelacion_bloquea_webpay_aun_inicializado(app, client):
    solicitud = preparar_solicitud(app, client)
    transaccion = TransaccionWebpayFalsa()
    app.config["WEBPAY_TRANSACCION_FACTORY"] = lambda: transaccion
    client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/webpay",
        json={},
    )

    respuesta = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/cancelar",
        json={},
    )

    assert respuesta.status_code == 202
    assert respuesta.get_json()["estado"] == "cancelacion_en_revision"
    assert respuesta.get_json()["codigo"] == "conciliacion_pago_no_disponible"


def test_cancelacion_detecta_autorizacion_webpay_y_activa_plan(app, client):
    solicitud = preparar_solicitud(app, client)
    transaccion = TransaccionWebpayFalsa()
    app.config["WEBPAY_TRANSACCION_FACTORY"] = lambda: transaccion
    inicio = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/webpay",
        json={},
    ).get_json()
    with app.app_context():
        pago = db.session.get(Pago, inicio["id"])
        sesion = pago.datos_proveedor["session_id"]
    transaccion.respuesta_estado = {
        "status": "AUTHORIZED",
        "response_code": 0,
        "buy_order": inicio["referencia_externa"],
        "session_id": sesion,
        "amount": solicitud["monto_esperado"],
        "authorization_code": "AUT-CONCILIADA",
        "payment_type_code": "VD",
        "installments_number": 0,
        "transaction_date": "2026-08-21T12:00:00Z",
        "accounting_date": "0821",
        "vci": "TSY",
        "card_detail": {"card_number": "6623"},
    }

    respuesta = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/cancelar",
        json={},
    )

    assert respuesta.status_code == 409
    with app.app_context():
        pago = db.session.get(Pago, inicio["id"])
        solicitud_db = db.session.get(SolicitudCambioPlan, solicitud["id"])
        assert pago.estado == "pagado"
        assert solicitud_db.estado == "aprobada"


def test_checkout_webpay_rechaza_sin_configuracion(
    app,
    client,
):
    solicitud = preparar_solicitud(
        app,
        client,
    )

    app.config["WEBPAY_TRANSACCION_FACTORY"] = None
    app.config["WEBPAY_COMMERCE_CODE"] = None
    app.config["WEBPAY_API_KEY"] = None

    respuesta = client.post(
        ("/api/suscripciones/solicitudes/" f"{solicitud['id']}" "/checkout/webpay"),
        json={},
    )

    assert respuesta.status_code == 503

    datos = respuesta.get_json()

    assert datos["codigo"] == "webpay_no_configurado"

    with app.app_context():
        assert db.session.scalar(db.select(Pago)) is None


def test_checkout_webpay_no_expone_credenciales(
    app,
    client,
):
    solicitud = preparar_solicitud(
        app,
        client,
    )
    transaccion = TransaccionWebpayFalsa()

    app.config.update(
        {
            "WEBPAY_TRANSACCION_FACTORY": (lambda: transaccion),
            "WEBPAY_COMMERCE_CODE": ("597055555532"),
            "WEBPAY_API_KEY": ("secreto-que-no-debe-salir"),
        }
    )

    respuesta = client.post(
        ("/api/suscripciones/solicitudes/" f"{solicitud['id']}" "/checkout/webpay"),
        json={},
    )

    cuerpo = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 201
    assert "597055555532" not in cuerpo
    assert "secreto-que-no-debe-salir" not in cuerpo


class TransaccionWebpayConfirmacionFalsa(TransaccionWebpayFalsa):
    def __init__(self):
        super().__init__()
        self.confirmaciones = []
        self.respuesta_confirmacion = None

    def commit(self, token):
        self.confirmaciones.append(token)

        if isinstance(
            self.respuesta_confirmacion,
            Exception,
        ):
            raise self.respuesta_confirmacion

        return self.respuesta_confirmacion


def iniciar_pago_confirmable(
    app,
    client,
):
    solicitud = preparar_solicitud(
        app,
        client,
    )
    transaccion = TransaccionWebpayConfirmacionFalsa()

    app.config["WEBPAY_TRANSACCION_FACTORY"] = lambda: transaccion

    respuesta = client.post(
        ("/api/suscripciones/solicitudes/" f"{solicitud['id']}" "/checkout/webpay"),
        json={},
    )

    assert respuesta.status_code == 201

    datos = respuesta.get_json()

    with app.app_context():
        pago = db.session.get(
            Pago,
            datos["id"],
        )

        session_id = pago.datos_proveedor["session_id"]

    return (
        solicitud,
        datos,
        session_id,
        transaccion,
    )


def respuesta_autorizada(
    *,
    pago,
    session_id,
    monto=None,
    referencia=None,
):
    return {
        "vci": "TSY",
        "amount": (monto if monto is not None else pago["monto"]),
        "status": "AUTHORIZED",
        "buy_order": (referencia if referencia is not None else pago["referencia_externa"]),
        "session_id": session_id,
        "card_detail": {
            "card_number": "6623",
        },
        "accounting_date": "0820",
        "transaction_date": ("2026-08-20T12:00:00.000Z"),
        "authorization_code": "1213",
        "payment_type_code": "VD",
        "response_code": 0,
        "installments_number": 0,
    }


def test_retorno_webpay_confirma_y_activa_plan(
    app,
    client,
):
    (
        solicitud,
        pago,
        session_id,
        transaccion,
    ) = iniciar_pago_confirmable(
        app,
        client,
    )

    transaccion.respuesta_confirmacion = respuesta_autorizada(
        pago=pago,
        session_id=session_id,
    )

    respuesta = client.post(
        "/webhooks/pagos/webpay/retorno",
        data={
            "token_ws": pago["token"],
        },
    )

    assert respuesta.status_code == 302
    assert "checkout=exito" in respuesta.headers["Location"]
    assert transaccion.confirmaciones == [
        pago["token"],
    ]

    with app.app_context():
        pago_db = db.session.get(
            Pago,
            pago["id"],
        )
        solicitud_db = db.session.get(
            SolicitudCambioPlan,
            solicitud["id"],
        )
        suscripcion = db.session.get(
            Suscripcion,
            pago_db.suscripcion_id,
        )
        plan = db.session.get(
            PlanSaaS,
            solicitud_db.plan_solicitado_id,
        )

        assert pago_db.estado == "pagado"
        assert pago_db.fecha_pago is not None
        assert pago_db.fecha_confirmacion is not None
        assert pago_db.datos_proveedor["status"] == "AUTHORIZED"
        assert pago_db.datos_proveedor["authorization_code"] == "1213"

        assert solicitud_db.estado == "aprobada"
        assert suscripcion.estado == "activa"
        assert suscripcion.plan_id == plan.id
        assert suscripcion.ciclo == solicitud["ciclo"]


def test_retorno_webpay_es_idempotente(
    app,
    client,
):
    (
        _solicitud,
        pago,
        session_id,
        transaccion,
    ) = iniciar_pago_confirmable(
        app,
        client,
    )

    transaccion.respuesta_confirmacion = respuesta_autorizada(
        pago=pago,
        session_id=session_id,
    )

    primera = client.post(
        "/webhooks/pagos/webpay/retorno",
        data={
            "token_ws": pago["token"],
        },
    )
    segunda = client.post(
        "/webhooks/pagos/webpay/retorno",
        data={
            "token_ws": pago["token"],
        },
    )

    assert primera.status_code == 302
    assert segunda.status_code == 302
    assert transaccion.confirmaciones == [
        pago["token"],
    ]

    with app.app_context():
        pago_db = db.session.get(
            Pago,
            pago["id"],
        )

        assert pago_db.estado == "pagado"


def test_retorno_webpay_rechaza_monto_distinto(
    app,
    client,
):
    (
        solicitud,
        pago,
        session_id,
        transaccion,
    ) = iniciar_pago_confirmable(
        app,
        client,
    )

    transaccion.respuesta_confirmacion = respuesta_autorizada(
        pago=pago,
        session_id=session_id,
        monto="1.00",
    )

    respuesta = client.post(
        "/webhooks/pagos/webpay/retorno",
        data={
            "token_ws": pago["token"],
        },
    )

    assert respuesta.status_code == 409

    with app.app_context():
        pago_db = db.session.get(
            Pago,
            pago["id"],
        )
        solicitud_db = db.session.get(
            SolicitudCambioPlan,
            solicitud["id"],
        )
        suscripcion = db.session.get(
            Suscripcion,
            pago_db.suscripcion_id,
        )

        assert pago_db.estado == "incidencia"
        assert solicitud_db.estado == "cancelacion_en_revision"
        assert suscripcion.ciclo == "prueba"


def test_retorno_webpay_rechaza_orden_distinta(
    app,
    client,
):
    (
        solicitud,
        pago,
        session_id,
        transaccion,
    ) = iniciar_pago_confirmable(
        app,
        client,
    )

    transaccion.respuesta_confirmacion = respuesta_autorizada(
        pago=pago,
        session_id=session_id,
        referencia="ORDEN-AJENA",
    )

    respuesta = client.post(
        "/webhooks/pagos/webpay/retorno",
        data={
            "token_ws": pago["token"],
        },
    )

    assert respuesta.status_code == 409

    with app.app_context():
        pago_db = db.session.get(
            Pago,
            pago["id"],
        )
        solicitud_db = db.session.get(
            SolicitudCambioPlan,
            solicitud["id"],
        )

        assert pago_db.estado == "incidencia"
        assert solicitud_db.estado == "cancelacion_en_revision"


def test_retorno_webpay_rechaza_token_desconocido(
    app,
    client,
):
    _preparar(app, client)

    transaccion = TransaccionWebpayConfirmacionFalsa()
    app.config["WEBPAY_TRANSACCION_FACTORY"] = lambda: transaccion

    respuesta = client.post(
        "/webhooks/pagos/webpay/retorno",
        data={
            "token_ws": "TOKEN-DESCONOCIDO",
        },
    )

    assert respuesta.status_code == 400
    assert transaccion.confirmaciones == []

    datos = respuesta.get_json()

    assert datos["codigo"] == "token_webpay_invalido"


def test_cliente_rest_webpay_usa_integracion(
    monkeypatch,
):
    from app.services.pagos_webpay import (
        obtener_transaccion_webpay,
    )

    llamadas = []

    def solicitar(metodo, url, **kwargs):
        llamadas.append((metodo, url, kwargs))

        class Respuesta:
            def raise_for_status(self):
                return None

            def json(self):
                return {"token": "token", "url": "https://webpay.test"}

        return Respuesta()

    monkeypatch.setattr("app.services.pagos_webpay.requests.request", solicitar)

    resultado = obtener_transaccion_webpay(
        {
            "WEBPAY_TRANSACCION_FACTORY": None,
            "WEBPAY_COMMERCE_CODE": "597055555532",
            "WEBPAY_API_KEY": "api-key-integracion",
            "WEBPAY_ENV": "integration",
        }
    )

    respuesta = resultado.create("orden", "sesion", Decimal("1234.00"), "https://retorno")

    assert respuesta["token"] == "token"
    metodo, url, opciones = llamadas[0]
    assert metodo == "POST"
    assert url == (
        "https://webpay3gint.transbank.cl/rswebpaytransaction/" "api/webpay/v1.2/transactions"
    )
    assert opciones["headers"]["Tbk-Api-Key-Id"] == "597055555532"
    assert opciones["headers"]["Tbk-Api-Key-Secret"] == "api-key-integracion"
    assert opciones["json"]["amount"] == 1234
    assert opciones["timeout"] == (5, 20)


def test_cliente_rest_webpay_usa_produccion(
    monkeypatch,
):
    from app.services.pagos_webpay import (
        obtener_transaccion_webpay,
    )

    llamadas = []

    def solicitar(metodo, url, **kwargs):
        llamadas.append((metodo, url, kwargs))

        class Respuesta:
            def raise_for_status(self):
                return None

            def json(self):
                return {"status": "AUTHORIZED"}

        return Respuesta()

    monkeypatch.setattr("app.services.pagos_webpay.requests.request", solicitar)

    resultado = obtener_transaccion_webpay(
        {
            "WEBPAY_TRANSACCION_FACTORY": None,
            "WEBPAY_COMMERCE_CODE": "codigo-productivo",
            "WEBPAY_API_KEY": "api-key-productiva",
            "WEBPAY_ENV": "production",
        }
    )

    assert resultado.commit("token/con-barra") == {"status": "AUTHORIZED"}
    metodo, url, opciones = llamadas[0]
    assert metodo == "PUT"
    assert url == (
        "https://webpay3g.transbank.cl/rswebpaytransaction/"
        "api/webpay/v1.2/transactions/token%2Fcon-barra"
    )
    assert opciones["headers"]["Tbk-Api-Key-Id"] == "codigo-productivo"
    assert opciones["headers"]["Tbk-Api-Key-Secret"] == "api-key-productiva"


def test_cliente_oficial_rechaza_ambiente_invalido():
    from app.services.pagos_webpay import (
        WebpayNoConfigurado,
        obtener_transaccion_webpay,
    )

    import pytest

    with pytest.raises(
        WebpayNoConfigurado,
        match="ambiente",
    ):
        obtener_transaccion_webpay(
            {
                "WEBPAY_TRANSACCION_FACTORY": None,
                "WEBPAY_COMMERCE_CODE": "597055555532",
                "WEBPAY_API_KEY": "api-key",
                "WEBPAY_ENV": "ambiente-inventado",
            }
        )
