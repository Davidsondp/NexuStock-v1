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
            email="clientes.global@nexustock.cl",
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
            "email": "clientes.global@nexustock.cl",
            "password": "ClaveSuperAdmin123",
        },
    )


def test_panel_clientes_exige_autenticacion(client):
    respuesta = client.get("/panel/clientes")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_usuario_empresarial_puede_ver_clientes(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/clientes")

    assert respuesta.status_code == 200
    assert "Clientes".encode("utf-8") in respuesta.data
    assert REGISTRO["empresa_nombre"].encode("utf-8") in respuesta.data


def test_superadmin_no_accede_a_clientes_empresariales(
    app,
    client,
):
    crear_superadmin(app)
    iniciar_superadmin(client)

    respuesta = client.get("/panel/clientes")

    assert respuesta.status_code == 403


def test_panel_empresarial_enlaza_modulo_clientes(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    assert b"/panel/clientes" in respuesta.data


def test_pagina_clientes_referencia_api_y_recursos(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/clientes")

    assert respuesta.status_code == 200
    assert b"/api/clientes" in respuesta.data
    assert b"css/panel_empresarial.css" in respuesta.data
    assert b"css/clientes.css" in respuesta.data
    assert b"js/clientes.js" in respuesta.data
    assert b' name="csrf_token"' in respuesta.data


def test_empleado_conserva_gestion_operativa_clientes(
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
            apellido="Clientes",
            email="empleado.clientes@nexustock.cl",
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
            "email": "empleado.clientes@nexustock.cl",
            "password": "ClaveEmpleado123",
        },
    )

    respuesta = client.get("/panel/clientes")

    assert respuesta.status_code == 200
    assert b'data-permiso-crear="true"' in respuesta.data
    assert b'data-permiso-editar="true"' in respuesta.data
    assert b'data-permiso-eliminar="false"' in respuesta.data
