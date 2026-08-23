from pathlib import Path

from app.models import Usuario, db
from tests.test_autenticacion import REGISTRO


def registrar_empresa(client):
    respuesta = client.post(
        "/autenticacion/registro",
        data=REGISTRO,
    )

    assert respuesta.status_code == 302


def habilitar_ubicaciones(app):
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        plan = usuario.empresa.suscripcion_actual.plan
        plan.funciones = {
            **(plan.funciones or {}),
            "multisucursal": True,
            "multibodega": True,
        }
        plan.limite_sucursales = 5
        plan.limite_bodegas = 10
        db.session.commit()


def ingresar_como_rol(
    app,
    client,
    rol,
):
    registrar_empresa(client)

    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        usuario.rol = rol
        db.session.commit()

    client.post("/autenticacion/salir")

    respuesta = client.post(
        "/autenticacion/ingresar",
        data={
            "email": REGISTRO["email"],
            "password": REGISTRO["password"],
        },
    )

    assert respuesta.status_code == 302


def test_panel_ubicaciones_requiere_ingreso(
    client,
):
    respuesta = client.get("/panel/administracion/ubicaciones")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_panel_ubicaciones_incluye_contrato_visual(
    app,
    client,
):
    registrar_empresa(client)
    habilitar_ubicaciones(app)

    respuesta = client.get("/panel/administracion/ubicaciones")

    assert respuesta.status_code == 200

    contratos = (
        b'data-api-sucursales="/api/sucursales"',
        b'data-api-bodegas="/api/bodegas"',
        b'data-api-usuarios="/api/usuarios"',
        b'data-limite-sucursales="5"',
        b'data-limite-bodegas="10"',
        b'data-puede-crear-sucursal="true"',
        b'data-puede-editar-sucursal="true"',
        b'data-puede-desactivar-sucursal="true"',
        b'data-puede-crear-bodega="true"',
        b'data-puede-editar-bodega="true"',
        b'data-puede-desactivar-bodega="true"',
        b'id="resumen-sucursales"',
        b'id="resumen-bodegas"',
        b'id="filtro-estado-ubicaciones"',
        b'id="lista-sucursales"',
        b'id="nueva-sucursal"',
        b'id="modal-sucursal"',
        b'id="formulario-sucursal"',
        b'id="sucursal-id"',
        b'id="sucursal-codigo"',
        b'id="sucursal-nombre"',
        b'id="sucursal-direccion"',
        b'id="sucursal-ciudad"',
        b'id="sucursal-telefono"',
        b'id="sucursal-crear-bodega"',
        b'id="guardar-sucursal"',
        b'id="cancelar-sucursal"',
        b'id="modal-bodega"',
        b'id="formulario-bodega"',
        b'id="bodega-id"',
        b'id="bodega-sucursal-id"',
        b'id="bodega-codigo"',
        b'id="bodega-nombre"',
        b'id="bodega-descripcion"',
        b'id="guardar-bodega"',
        b'id="cancelar-bodega"',
        b'id="modal-usuarios-sucursal"',
        b'id="lista-usuarios-sucursal"',
        b'id="cerrar-usuarios-sucursal"',
        b"css/ubicaciones.css",
        b"js/ubicaciones.js",
    )

    for contrato in contratos:
        assert contrato in respuesta.data

    textos = (
        "Sucursales y bodegas",
        "Estructura operacional",
        "Límite del plan",
        "La desactivación se bloquea",
        "stock o transferencias pendientes",
    )

    for texto in textos:
        assert texto.encode("utf-8") in respuesta.data


def test_panel_ubicaciones_rechaza_empleado(
    app,
    client,
):
    ingresar_como_rol(
        app,
        client,
        "empleado",
    )

    respuesta = client.get("/panel/administracion/ubicaciones")

    assert respuesta.status_code == 403


def test_panel_ubicaciones_rechaza_supervisor(
    app,
    client,
):
    ingresar_como_rol(
        app,
        client,
        "supervisor",
    )

    respuesta = client.get("/panel/administracion/ubicaciones")

    assert respuesta.status_code == 403


def test_panel_principal_enlaza_ubicaciones(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    assert b"/panel/administracion/ubicaciones" in respuesta.data
    assert "Sucursales y bodegas".encode("utf-8") in respuesta.data


def test_javascript_ubicaciones_integra_api():
    contenido = Path("app/static/js/ubicaciones.js").read_text(encoding="utf-8-sig")

    contratos = (
        "apiSucursales",
        "apiBodegas",
        "apiUsuarios",
        "incluir_inactivas",
        "/reactivar",
        "/usuarios/",
        "modal-sucursal",
        "modal-bodega",
        "modal-usuarios-sucursal",
        "X-CSRFToken",
    )

    for contrato in contratos:
        assert contrato in contenido
