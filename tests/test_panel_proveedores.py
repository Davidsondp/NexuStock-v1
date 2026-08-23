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
            email="proveedores.global@nexustock.cl",
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
            "email": "proveedores.global@nexustock.cl",
            "password": "ClaveSuperAdmin123",
        },
    )


def test_panel_proveedores_exige_autenticacion(client):
    respuesta = client.get("/panel/proveedores")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_usuario_empresarial_puede_ver_proveedores(
    app,
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/proveedores")

    assert respuesta.status_code == 200
    assert "Proveedores".encode("utf-8") in respuesta.data
    assert REGISTRO["empresa_nombre"].encode("utf-8") in respuesta.data


def test_superadmin_no_accede_a_proveedores_empresariales(
    app,
    client,
):
    crear_superadmin(app)
    iniciar_superadmin(client)

    respuesta = client.get("/panel/proveedores")

    assert respuesta.status_code == 403


def test_panel_empresarial_enlaza_modulo_proveedores(client):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    assert b"/panel/proveedores" in respuesta.data


def test_pagina_proveedores_referencia_api_empresarial(
    app,
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/proveedores")

    assert respuesta.status_code == 200
    assert b"/api/proveedores" in respuesta.data


def test_empleado_no_ve_acciones_de_proveedores(
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
            email="empleado.proveedores@nexustock.cl",
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
            "email": "empleado.proveedores@nexustock.cl",
            "password": "ClaveEmpleado123",
        },
    )

    respuesta = client.get("/panel/proveedores")

    assert respuesta.status_code == 200
    assert b'data-permiso-crear="false"' in respuesta.data
    assert b'data-permiso-editar="false"' in respuesta.data
    assert b'data-permiso-eliminar="false"' in respuesta.data
