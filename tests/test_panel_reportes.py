from pathlib import Path

from app.models import Usuario, db
from tests.test_autenticacion import REGISTRO


def registrar_empresa(client):
    return client.post(
        "/autenticacion/registro",
        data=REGISTRO,
    )


def test_panel_reportes_exige_autenticacion(
    client,
):
    respuesta = client.get("/panel/reportes")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_panel_reportes_expone_interfaz_empresarial(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/reportes")

    assert respuesta.status_code == 200

    contratos = (
        b'data-api-stock="/api/reportes/stock"',
        (b'data-api-movimientos="' b'/api/reportes/movimientos"'),
        (b'data-api-analitica="' b'/api/reportes/analitica"'),
        b'data-bodega-id="',
        b'id="filtro-desde-reportes"',
        b'id="filtro-hasta-reportes"',
        b'id="actualizar-reportes"',
        b'id="resumen-valor-inventario"',
        b'id="resumen-stock-total"',
        b'id="resumen-stock-disponible"',
        b'id="tabla-stock-reportes"',
        b'id="tabla-movimientos-reportes"',
        b'id="seccion-analitica-reportes"',
        b'id="productos-mas-vendidos"',
        b'id="productos-sin-movimiento"',
        b'id="productos-sobrestock"',
        b"css/reportes.css",
        b"js/reportes.js",
    )

    for contrato in contratos:
        assert contrato in respuesta.data

    textos = (
        "Centro de reportes",
        "Inventario valorizado",
        "Movimientos recientes",
        "Analítica operacional",
    )

    for texto in textos:
        assert texto.encode("utf-8") in respuesta.data


def test_panel_reportes_expone_capacidades_efectivas(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/reportes")

    assert respuesta.status_code == 200

    contratos = (
        b'data-permiso-analitica="',
        b'data-permiso-exportar="',
        b'data-permiso-ejecutivo="',
    )

    for contrato in contratos:
        assert contrato in respuesta.data


def test_empleado_no_accede_panel_reportes(
    app,
    client,
):
    registrar_empresa(client)

    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario).where(Usuario.email == REGISTRO["email"]))
        usuario.rol = "empleado"
        db.session.commit()
        db.session.expire_all()

    client.post("/autenticacion/salir")

    ingreso = client.post(
        "/autenticacion/ingresar",
        data={
            "email": REGISTRO["email"],
            "password": REGISTRO["password"],
        },
    )

    assert ingreso.status_code == 302

    respuesta = client.get("/panel/reportes")

    assert respuesta.status_code == 403


def test_paneles_enlazan_centro_reportes():
    plantillas = (
        "alertas.html",
        "clientes.html",
        "compras.html",
        "inicio.html",
        "inventario.html",
        "productos.html",
        "proveedores.html",
        "ventas.html",
    )

    for nombre in plantillas:
        contenido = Path("app/templates/panel").joinpath(nombre).read_text(encoding="utf-8-sig")

        assert "url_for('panel.reportes')" in contenido or (
            "url_for(\n" "                        " "'panel.reportes'" in contenido
        )
        assert 'href="/api/reportes/stock"' not in contenido


def test_javascript_reportes_integra_backend():
    contenido = Path("app/static/js/reportes.js").read_text(encoding="utf-8-sig")

    contratos = (
        "apiStock",
        "apiMovimientos",
        "apiAnalitica",
        "permisoAnalitica",
        "filtro-desde-reportes",
        "filtro-hasta-reportes",
        "tabla-stock-reportes",
        "tabla-movimientos-reportes",
        "productos-mas-vendidos",
        "productos-sin-movimiento",
        "productos-sobrestock",
        "bodega_id",
    )

    for contrato in contratos:
        assert contrato in contenido
