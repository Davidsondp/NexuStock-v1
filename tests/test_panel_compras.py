from pathlib import Path

from app.models import Usuario, UsuarioSucursal, db
from tests.test_autenticacion import REGISTRO


def registrar_empresa(client):
    return client.post(
        "/autenticacion/registro",
        data=REGISTRO,
    )


def crear_superadmin(app):
    with app.app_context():
        usuario = Usuario(
            empresa_id=None,
            nombre="Super",
            apellido="Administrador",
            email="compras.global@nexustock.cl",
            rol="super_admin",
            activo=True,
        )
        usuario.set_password("ClaveSuperAdmin123")

        db.session.add(usuario)
        db.session.commit()


def iniciar_superadmin(client):
    return client.post(
        "/autenticacion/ingresar",
        data={
            "email": "compras.global@nexustock.cl",
            "password": "ClaveSuperAdmin123",
        },
    )


def test_panel_compras_exige_autenticacion(client):
    respuesta = client.get("/panel/compras")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_usuario_empresarial_puede_ver_compras(
    app,
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/compras")

    assert respuesta.status_code == 200
    assert "Compras".encode("utf-8") in respuesta.data
    assert REGISTRO["empresa_nombre"].encode("utf-8") in respuesta.data


def test_superadmin_no_accede_a_compras_empresariales(
    app,
    client,
):
    crear_superadmin(app)
    iniciar_superadmin(client)

    respuesta = client.get("/panel/compras")

    assert respuesta.status_code == 403


def test_panel_empresarial_enlaza_modulo_compras(client):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    assert b"/panel/compras" in respuesta.data


def test_pagina_compras_referencia_apis_empresariales(
    app,
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/compras")

    assert respuesta.status_code == 200
    assert b"/api/compras" in respuesta.data
    assert b"/api/proveedores" in respuesta.data
    assert b"/api/productos" in respuesta.data


def test_empleado_ve_compras_sin_acciones_operativas(
    app,
    client,
):
    registrar_empresa(client)

    with app.app_context():
        administrador = db.session.scalar(
            db.select(Usuario).where(Usuario.email == REGISTRO["email"])
        )

        empleado = Usuario(
            empresa_id=administrador.empresa_id,
            nombre="Empleado",
            apellido="Consulta",
            email="empleado.compras@nexustock.cl",
            rol="empleado",
            activo=True,
        )
        empleado.set_password("ClaveEmpleado123")

        db.session.add(empleado)
        db.session.flush()

        asignacion_principal = db.session.scalar(
            db.select(UsuarioSucursal).where(
                UsuarioSucursal.empresa_id == administrador.empresa_id,
                UsuarioSucursal.usuario_id == administrador.id,
                UsuarioSucursal.es_principal.is_(True),
            )
        )

        db.session.add(
            UsuarioSucursal(
                empresa_id=administrador.empresa_id,
                usuario_id=empleado.id,
                sucursal_id=asignacion_principal.sucursal_id,
                es_principal=True,
            )
        )

        db.session.commit()

    client.post("/autenticacion/salir")

    client.post(
        "/autenticacion/ingresar",
        data={
            "email": "empleado.compras@nexustock.cl",
            "password": "ClaveEmpleado123",
        },
    )

    respuesta = client.get("/panel/compras")

    assert respuesta.status_code == 200
    assert b'data-permiso-crear="false"' in respuesta.data
    assert b'data-permiso-editar="false"' in respuesta.data
    assert b'data-permiso-enviar="false"' in respuesta.data
    assert b'data-permiso-recibir="false"' in respuesta.data
    assert b'data-permiso-cancelar="false"' in respuesta.data


def test_panel_compras_explica_presentaciones(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/compras")

    assert respuesta.status_code == 200
    assert "Compra por unidad base o presentación".encode("utf-8") in respuesta.data
    assert (
        "El inventario se actualizará "
        "automáticamente en la unidad base".encode("utf-8") in respuesta.data
    )


def test_javascript_compras_integra_presentaciones():
    contenido = Path("app/static/js/compras.js").read_text(encoding="utf-8-sig")

    contratos = (
        "linea-presentacion",
        "/presentaciones",
        "cantidad_presentacion",
        "factor_conversion",
        "precio_presentacion",
        "costo_presentacion",
    )

    for contrato in contratos:
        assert contrato in contenido
