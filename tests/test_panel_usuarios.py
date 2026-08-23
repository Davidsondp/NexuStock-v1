from pathlib import Path

from app.models import Usuario, db
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
        db.session.expire_all()

    client.post("/autenticacion/salir")

    return client.post(
        "/autenticacion/ingresar",
        data={
            "email": REGISTRO["email"],
            "password": REGISTRO["password"],
        },
    )


def test_panel_usuarios_exige_autenticacion(
    client,
):
    respuesta = client.get("/panel/administracion/usuarios")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_admin_accede_gestion_usuarios(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/administracion/usuarios")

    assert respuesta.status_code == 200

    contratos = (
        b'data-api-usuarios="/api/usuarios"',
        b'data-api-sucursales="/api/sucursales"',
        b'data-usuario-actual-id="',
        b'data-limite-usuarios="',
        b'data-permiso-crear="true"',
        b'data-permiso-editar="true"',
        b'data-permiso-desactivar="true"',
        b'data-permiso-roles="true"',
        b'id="resumen-usuarios-activos"',
        b'id="resumen-limite-usuarios"',
        b'id="filtro-estado-usuarios"',
        b'id="lista-usuarios"',
        b'id="abrir-formulario-usuario"',
        b'id="formulario-usuario"',
        b'id="usuario-id"',
        b'id="usuario-nombre"',
        b'id="usuario-apellido"',
        b'id="usuario-email"',
        b'id="usuario-rut"',
        b'id="usuario-telefono"',
        b'id="usuario-password"',
        b'id="usuario-rol"',
        b'id="usuario-sucursales"',
        b'id="contenedor-permisos-especiales"',
        b'id="guardar-usuario"',
        b'id="cancelar-usuario"',
        b"css/usuarios.css",
        b"js/usuarios.js",
    )

    for contrato in contratos:
        assert contrato in respuesta.data

    textos = (
        "Administración de usuarios",
        "Equipo y accesos",
        "Sucursales asignadas",
        "Permisos especiales",
    )

    for texto in textos:
        assert texto.encode("utf-8") in respuesta.data


def test_empleado_no_accede_gestion_usuarios(
    app,
    client,
):
    registrar_empresa(client)

    ingreso = convertir_en_empleado(
        app,
        client,
        "empleado",
    )

    assert ingreso.status_code == 302

    respuesta = client.get("/panel/administracion/usuarios")

    assert respuesta.status_code == 403


def test_supervisor_no_accede_gestion_usuarios(
    app,
    client,
):
    registrar_empresa(client)

    ingreso = convertir_en_empleado(
        app,
        client,
        "supervisor",
    )

    assert ingreso.status_code == 302

    respuesta = client.get("/panel/administracion/usuarios")

    assert respuesta.status_code == 403


def test_panel_principal_enlaza_administracion(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    assert b"/panel/administracion/usuarios" in respuesta.data
    assert "Administración".encode("utf-8") in respuesta.data


def test_javascript_usuarios_integra_api():
    contenido = Path("app/static/js/usuarios.js").read_text(encoding="utf-8-sig")

    contratos = (
        "apiUsuarios",
        "apiSucursales",
        "permisoCrear",
        "permisoEditar",
        "permisoDesactivar",
        "permisoRoles",
        "incluir_inactivos",
        "cambiar-password",
        "desactivar",
        "reactivar",
        "revocar-sesiones",
        "usuario-sucursales",
        "contenedor-permisos-especiales",
        "X-CSRFToken",
    )

    for contrato in contratos:
        assert contrato in contenido
