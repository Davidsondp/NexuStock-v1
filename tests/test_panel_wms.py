from pathlib import Path
from app.models import Usuario, db
from tests.test_suite_comercial import _preparar


def test_panel_wms_carga_interfaz_y_escaner(
    app,
    client,
):
    _preparar(app, client)

    respuesta = client.get("/panel/wms")

    assert respuesta.status_code == 200

    plantilla = respuesta.data.decode("utf-8")

    esperados = (
        "Picking y packing",
        'id="lista-ordenes-wms"',
        'id="video-escaner-wms"',
        'id="cantidad-escaner-wms"',
        'id="despacho-wms"',
        "zxing-browser-0.1.5.min.js",
        "js/escaner.js",
        "js/wms.js",
    )

    for esperado in esperados:
        assert esperado in plantilla

    assert (
        plantilla.index("zxing-browser-0.1.5.min.js")
        < plantilla.index("js/escaner.js")
        < plantilla.index("js/wms.js")
    )


def test_panel_y_consultas_wms_respetan_plan(
    app,
    client,
):
    usuario_id, *_otros = _preparar(
        app,
        client,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        plan = usuario.empresa.suscripcion_actual.plan
        plan.funciones = {
            **(plan.funciones or {}),
            "wms": False,
        }
        db.session.commit()

    panel = client.get("/panel/wms")
    api = client.get("/api/comercial/wms/ordenes")

    assert panel.status_code == 403
    assert api.status_code == 403
    assert api.get_json()["codigo"] == "plan_insuficiente"


def test_ventas_ofrece_acceso_al_panel_wms():
    plantilla = Path("app/templates/panel/ventas.html").read_text(encoding="utf-8-sig")

    assert "Picking y packing" in plantilla
    assert "url_for('panel.wms')" in plantilla


def test_javascript_wms_reutiliza_escaner_y_endpoints():
    javascript = Path("app/static/js/wms.js").read_text(encoding="utf-8-sig")

    esperados = (
        "NexuEscaner.crear",
        "/avanzar",
        "/escanear",
        "codigo_producto",
        "cantidad",
        "transportista",
        "seguimiento",
        "pagehide",
    )

    for esperado in esperados:
        assert esperado in javascript

    assert "getUserMedia" not in javascript
    assert "new BarcodeDetector" not in javascript


def test_ventas_oculta_wms_si_plan_no_lo_incluye(
    app,
    client,
):
    usuario_id, *_otros = _preparar(
        app,
        client,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        plan = usuario.empresa.suscripcion_actual.plan
        plan.funciones = {
            **(plan.funciones or {}),
            "wms": False,
        }
        db.session.commit()

    restringida = client.get("/panel/ventas")

    assert restringida.status_code == 200
    assert b"Picking y packing" not in restringida.data
