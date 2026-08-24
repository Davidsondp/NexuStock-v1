from pathlib import Path
from datetime import timedelta

from app.models import Suscripcion, Usuario, db, utcnow
from tests.test_autenticacion import REGISTRO


def registrar_empresa(client):
    return client.post(
        "/autenticacion/registro",
        data=REGISTRO,
    )


def convertir_en_empleado(
    app,
    client,
    rol="empleado",
):
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario).where(Usuario.email == REGISTRO["email"]))
        usuario.rol = rol
        db.session.commit()

    client.post("/autenticacion/salir")

    ingreso = client.post(
        "/autenticacion/ingresar",
        data={
            "email": REGISTRO["email"],
            "password": REGISTRO["password"],
        },
    )

    assert ingreso.status_code == 302


def test_panel_planes_requiere_autenticacion(
    client,
):
    respuesta = client.get("/panel/administracion/planes")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_panel_planes_incluye_contrato_visual(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/administracion/planes")

    assert respuesta.status_code == 200

    contratos = (
        b'data-api-suscripciones="/api/suscripciones"',
        b'data-puede-solicitar="true"',
        b'id="resumen-plan-actual"',
        b'id="resumen-estado-suscripcion"',
        b'id="resumen-vigencia"',
        b'id="resumen-ciclo"',
        b'id="lista-limites-plan"',
        b'id="selector-ciclo"',
        b'id="selector-proveedor"',
        b'id="lista-planes"',
        b'id="comparador-capacidades"',
        b'id="historial-solicitudes"',
        b'id="estado-planes"',
        b'id="actualizar-planes"',
        b'class="flujo-planes"',
        b'id="boton-activar-mandato"',
        b'id="mandato-plan-nombre"',
        b'id="mandato-proveedor-nombre"',
        b"css/planes.css",
        b"js/planes.js",
    )

    for contrato in contratos:
        assert contrato in respuesta.data

    textos = (
        "Planes y suscripci\u00f3n",
        "Un plan que crece con tu inventario",
        "Autoriza tu medio de pago",
        "Sin cobro hoy",
        "Plan actual",
        "Capacidades de NexuStock",
        "Inteligencia artificial",
        "Disponible",
        "Seguimiento de la solicitud",
    )

    for texto in textos:
        assert texto.encode("utf-8") in respuesta.data

    assert b'name="card_number"' not in respuesta.data
    assert b'name="cvv"' not in respuesta.data


def test_panel_planes_rechaza_empleado(
    app,
    client,
):
    registrar_empresa(client)
    convertir_en_empleado(
        app,
        client,
        rol="empleado",
    )

    respuesta = client.get("/panel/administracion/planes")

    assert respuesta.status_code == 403


def test_panel_planes_rechaza_supervisor(
    app,
    client,
):
    registrar_empresa(client)
    convertir_en_empleado(
        app,
        client,
        rol="supervisor",
    )

    respuesta = client.get("/panel/administracion/planes")

    assert respuesta.status_code == 403


def test_jefe_con_suscripcion_vencida_puede_renovar_pero_no_operar(app, client):
    registrar_empresa(client)
    with app.app_context():
        suscripcion = db.session.scalar(db.select(Suscripcion))
        suscripcion.fecha_inicio = utcnow() - timedelta(days=31)
        suscripcion.fecha_fin = utcnow() - timedelta(minutes=1)
        db.session.commit()
        db.session.expire_all()
    client.post("/autenticacion/salir")
    client.post(
        "/autenticacion/ingresar",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )

    assert client.get("/panel/administracion/planes").status_code == 200
    assert client.get("/panel").status_code == 403


def test_panel_principal_enlaza_planes(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    assert b"/panel/administracion/planes" in respuesta.data
    assert "Planes y suscripci\u00f3n".encode("utf-8") in respuesta.data


def test_javascript_planes_declara_contratos():
    contenido = Path("app/static/js/planes.js").read_text(encoding="utf-8-sig")

    contratos = (
        "apiSuscripciones",
        "planes_disponibles",
        "catalogo_capacidades",
        "capacidades",
        "plan_codigo",
        "ciclo",
        "/solicitudes",
        "/cancelar",
        "X-CSRFToken",
        "selector-ciclo",
        "comparador-capacidades",
        "historial-solicitudes",
    )

    for contrato in contratos:
        assert contrato in contenido


def test_panel_planes_incluye_checkout_webpay(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/administracion/planes")

    assert respuesta.status_code == 200

    contratos = (
        (b"data-checkout-webpay-sufijo=" b'"/checkout/webpay"'),
        (b'id="formulario-redireccion-' b'webpay"'),
        b'method="post"',
        b'id="token-ws-webpay"',
        b'name="token_ws"',
        b'id="estado-checkout"',
    )

    for contrato in contratos:
        assert contrato in respuesta.data

    assert "Anual ? mejor valor".encode("utf-8") in respuesta.data


def test_javascript_planes_conecta_checkout_webpay():
    contenido = Path("app/static/js/planes.js").read_text(encoding="utf-8-sig")

    contratos = (
        "checkoutWebpaySufijo",
        "iniciarCheckoutWebpay",
        "redireccionarAWebpay",
        "formulario-redireccion-webpay",
        "token-ws-webpay",
        "estado-checkout",
        "url_redireccion",
        "token_ws",
        "solicitud.id",
        "formulario.action",
        "formulario.submit()",
    )

    for contrato in contratos:
        assert contrato in contenido


def test_panel_planes_conecta_checkout_mercadopago(client):
    registrar_empresa(client)
    respuesta = client.get("/panel/administracion/planes")
    assert respuesta.status_code == 200
    assert b'data-checkout-mercadopago-sufijo="/checkout/mercadopago"' in respuesta.data

    contenido = Path("app/static/js/planes.js").read_text(encoding="utf-8-sig")
    for contrato in (
        "checkoutMercadoPagoSufijo",
        "iniciarCheckoutMercadoPago",
        "window.location.assign",
        "/checkout/mercadopago",
    ):
        assert contrato in contenido
