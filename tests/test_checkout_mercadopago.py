import hashlib
import hmac
import time

from app.models import Pago, SolicitudCambioPlan, Suscripcion, db
from tests.test_checkout_webpay import preparar_solicitud


class ClienteMercadoPagoFalso:
    def __init__(self):
        self.preferencias = []
        self.pagos = {}
        self.resultados_busqueda = []
        self.preferencias_expiradas = []

    def crear_preferencia(self, datos, clave_idempotencia):
        self.preferencias.append((datos, clave_idempotencia))
        return {
            "id": "PREFERENCIA-PRUEBA",
            "init_point": "https://www.mercadopago.cl/checkout/v1/redirect",
            "sandbox_init_point": "https://sandbox.mercadopago.cl/checkout/v1/redirect",
        }

    def obtener_pago(self, pago_id):
        return self.pagos[str(pago_id)]

    def buscar_pagos(self, _referencia_externa):
        return list(self.resultados_busqueda)

    def expirar_preferencia(self, preferencia_id):
        self.preferencias_expiradas.append(preferencia_id)
        return {"id": preferencia_id, "expires": True}


class ClienteMercadoPagoSinRespuesta(ClienteMercadoPagoFalso):
    def crear_preferencia(self, datos, clave_idempotencia):
        raise TimeoutError("sin respuesta")


def _configurar(app, cliente):
    app.config.update(
        {
            "BASE_URL": "https://nexustock.example",
            "MERCADOPAGO_ENV": "production",
            "MERCADOPAGO_CLIENTE_FACTORY": lambda: cliente,
            "MERCADOPAGO_WEBHOOK_SECRET": "firma-secreta-mercadopago-123456789",
        }
    )


def _firma(secreto, data_id, request_id, ts=None):
    ts = str(int(time.time())) if ts is None else str(ts)
    manifiesto = f"id:{data_id};request-id:{request_id};ts:{ts};"
    digest = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={digest}"


def _metadata_pago(app, inicio, solicitud):
    with app.app_context():
        pago = db.session.get(Pago, inicio["id"])
        return {
            "pago_id": str(pago.id),
            "empresa_id": str(pago.empresa_id),
            "solicitud_id": str(solicitud["id"]),
        }


def test_checkout_mercadopago_crea_preferencia_servidor(app, client):
    solicitud = preparar_solicitud(app, client, "mercadopago")
    proveedor = ClienteMercadoPagoFalso()
    _configurar(app, proveedor)

    respuesta = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/mercadopago",
        json={"monto": "1", "moneda": "USD"},
    )

    assert respuesta.status_code == 201
    datos = respuesta.get_json()
    assert datos["proveedor"] == "mercadopago"
    assert datos["url_redireccion"].startswith("https://www.mercadopago.cl/")
    preferencia, clave = proveedor.preferencias[0]
    assert preferencia["external_reference"] == clave == datos["referencia_externa"]
    assert preferencia["items"][0]["currency_id"] == "CLP"
    assert preferencia["items"][0]["unit_price"] == float(solicitud["monto_esperado"])
    assert preferencia["notification_url"] == (
        "https://nexustock.example/webhooks/pagos/mercadopago"
    )
    assert preferencia["expires"] is True
    assert preferencia["expiration_date_to"] > preferencia["expiration_date_from"]
    with app.app_context():
        pago = db.session.get(Pago, datos["id"])
        assert pago.fecha_vencimiento is not None
        assert pago.token_proveedor == "PREFERENCIA-PRUEBA"


def test_checkout_mercadopago_reutiliza_preferencia(app, client):
    solicitud = preparar_solicitud(app, client, "mercadopago")
    proveedor = ClienteMercadoPagoFalso()
    _configurar(app, proveedor)
    ruta = f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/mercadopago"

    primera = client.post(ruta, json={})
    segunda = client.post(ruta, json={})

    assert primera.status_code == 201
    assert segunda.status_code == 200
    assert primera.get_json()["id"] == segunda.get_json()["id"]
    assert len(proveedor.preferencias) == 1


def test_mercadopago_sin_respuesta_conserva_intento_para_conciliar(app, client):
    solicitud = preparar_solicitud(app, client, "mercadopago")
    proveedor = ClienteMercadoPagoSinRespuesta()
    _configurar(app, proveedor)
    ruta = f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/mercadopago"
    primera = client.post(ruta, json={})
    segunda = client.post(ruta, json={})
    assert primera.status_code == 502
    assert segunda.status_code == 400
    with app.app_context():
        pagos = list(db.session.scalars(db.select(Pago)))
        solicitud_db = db.session.get(SolicitudCambioPlan, solicitud["id"])
        assert len(pagos) == 1
        assert pagos[0].estado == "iniciado"
        assert solicitud_db.estado == "cancelacion_en_revision"


def test_cancelacion_expira_preferencia_sin_pago_y_libera_solicitud(app, client):
    solicitud = preparar_solicitud(app, client, "mercadopago")
    proveedor = ClienteMercadoPagoFalso()
    _configurar(app, proveedor)
    inicio = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/mercadopago",
        json={},
    )
    assert inicio.status_code == 201

    respuesta = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/cancelar",
        json={},
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "cancelada"
    assert proveedor.preferencias_expiradas == ["PREFERENCIA-PRUEBA"]
    with app.app_context():
        pago = db.session.get(Pago, inicio.get_json()["id"])
        assert pago.estado == "cancelado"


def test_cancelacion_detecta_pago_aprobado_mercadopago(app, client):
    solicitud = preparar_solicitud(app, client, "mercadopago")
    proveedor = ClienteMercadoPagoFalso()
    _configurar(app, proveedor)
    inicio = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/mercadopago",
        json={},
    ).get_json()
    proveedor.resultados_busqueda = [{"id": 123, "status": "approved"}]
    proveedor.pagos["123"] = {
        "id": 123,
        "status": "approved",
        "external_reference": inicio["referencia_externa"],
        "transaction_amount": solicitud["monto_esperado"],
        "currency_id": "CLP",
        "payment_type_id": "credit_card",
        "metadata": _metadata_pago(app, inicio, solicitud),
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


def test_webhook_mercadopago_consulta_y_activa_suscripcion(app, client):
    solicitud = preparar_solicitud(app, client, "mercadopago")
    proveedor = ClienteMercadoPagoFalso()
    _configurar(app, proveedor)
    inicio = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/mercadopago",
        json={},
    ).get_json()
    proveedor.pagos["987654"] = {
        "id": 987654,
        "status": "approved",
        "external_reference": inicio["referencia_externa"],
        "transaction_amount": solicitud["monto_esperado"],
        "currency_id": "CLP",
        "payment_type_id": "credit_card",
        "metadata": _metadata_pago(app, inicio, solicitud),
    }
    secreto = app.config["MERCADOPAGO_WEBHOOK_SECRET"]
    request_id = "request-mercadopago-1"

    respuesta = client.post(
        "/webhooks/pagos/mercadopago?data.id=987654",
        json={"type": "payment", "data": {"id": "987654"}},
        headers={
            "X-Request-Id": request_id,
            "X-Signature": _firma(secreto, "987654", request_id),
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "pagado"
    with app.app_context():
        pago = db.session.get(Pago, inicio["id"])
        solicitud_db = db.session.get(SolicitudCambioPlan, solicitud["id"])
        suscripcion = db.session.get(Suscripcion, pago.suscripcion_id)
        assert pago.estado == "pagado"
        assert solicitud_db.estado == "aprobada"
        assert suscripcion.plan_id == solicitud_db.plan_solicitado_id


def test_webhook_mercadopago_rechaza_firma_invalida(app, client):
    proveedor = ClienteMercadoPagoFalso()
    _configurar(app, proveedor)

    respuesta = client.post(
        "/webhooks/pagos/mercadopago?data.id=1",
        json={"data": {"id": "1"}},
        headers={"X-Request-Id": "r1", "X-Signature": "ts=1,v1=falsa"},
    )

    assert respuesta.status_code == 401
    assert proveedor.pagos == {}


def test_webhook_mercadopago_rechaza_firma_vencida(app, client):
    proveedor = ClienteMercadoPagoFalso()
    _configurar(app, proveedor)
    marca_vencida = int(time.time()) - 301

    respuesta = client.post(
        "/webhooks/pagos/mercadopago?data.id=1",
        json={"data": {"id": "1"}},
        headers={
            "X-Request-Id": "r-vencida",
            "X-Signature": _firma(
                app.config["MERCADOPAGO_WEBHOOK_SECRET"],
                "1",
                "r-vencida",
                marca_vencida,
            ),
        },
    )

    assert respuesta.status_code == 401
    assert proveedor.pagos == {}


def test_reembolso_mercadopago_suspende_plan_pagado(app, client):
    solicitud = preparar_solicitud(app, client, "mercadopago")
    proveedor = ClienteMercadoPagoFalso()
    _configurar(app, proveedor)
    inicio = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/mercadopago",
        json={},
    ).get_json()
    proveedor.pagos["987655"] = {
        "id": 987655,
        "status": "approved",
        "external_reference": inicio["referencia_externa"],
        "transaction_amount": solicitud["monto_esperado"],
        "currency_id": "CLP",
        "payment_type_id": "credit_card",
        "metadata": _metadata_pago(app, inicio, solicitud),
    }
    secreto = app.config["MERCADOPAGO_WEBHOOK_SECRET"]

    def notificar(request_id):
        return client.post(
            "/webhooks/pagos/mercadopago?data.id=987655",
            json={"type": "payment", "data": {"id": "987655"}},
            headers={
                "X-Request-Id": request_id,
                "X-Signature": _firma(secreto, "987655", request_id),
            },
        )

    assert notificar("pago-aprobado").status_code == 200
    proveedor.pagos["987655"]["status"] = "refunded"
    respuesta = notificar("pago-reembolsado")

    assert respuesta.status_code == 200
    with app.app_context():
        pago = db.session.get(Pago, inicio["id"])
        suscripcion = db.session.get(Suscripcion, pago.suscripcion_id)
        assert pago.estado == "reembolsado"
        assert suscripcion.estado == "suspendida"


def test_no_permite_dos_proveedores_activos(app, client):
    solicitud = preparar_solicitud(app, client, "mercadopago")
    proveedor = ClienteMercadoPagoFalso()
    _configurar(app, proveedor)
    ruta_mp = f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/mercadopago"
    assert client.post(ruta_mp, json={}).status_code == 201

    app.config["WEBPAY_TRANSACCION_FACTORY"] = lambda: object()
    respuesta = client.post(
        f"/api/suscripciones/solicitudes/{solicitud['id']}/checkout/webpay",
        json={},
    )

    assert respuesta.status_code == 409
    assert respuesta.get_json()["codigo"] == "conflicto_pago"
