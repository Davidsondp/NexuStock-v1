from app.models import Usuario, db
from app.services.contexto import CLAVE_BODEGA, CLAVE_SUCURSAL
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
            email="panel.global@nexustock.cl",
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
            "email": "panel.global@nexustock.cl",
            "password": "ClaveSuperAdmin123",
        },
    )


def test_panel_empresarial_exige_autenticacion(client):
    respuesta = client.get("/panel")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_empresa_con_una_ubicacion_entra_al_panel(app, client):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    assert "Panel empresarial".encode("utf-8") in respuesta.data
    assert REGISTRO["empresa_nombre"].encode("utf-8") in respuesta.data

    with client.session_transaction() as sesion:
        assert CLAVE_SUCURSAL in sesion
        assert CLAVE_BODEGA in sesion


def test_panel_principal_expone_dashboard_interactivo(client):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    assert b'class="bienvenida"' in respuesta.data
    assert b'id="salud-inventario"' in respuesta.data
    assert b'id="actualizar-panel"' in respuesta.data
    assert b'id="metrica-dinero-dormido"' in respuesta.data
    assert b"?escanear=1" in respuesta.data
    assert b"Preguntar a Nexu" not in respuesta.data


def test_superadmin_no_accede_al_panel_empresarial(app, client):
    crear_superadmin(app)
    iniciar_superadmin(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 403


def test_registro_redirige_al_panel_empresarial(client):
    respuesta = registrar_empresa(client)

    assert respuesta.status_code == 302
    assert respuesta.location.endswith("/panel")


def test_login_empresarial_redirige_al_panel(app, client):
    registrar_empresa(client)
    client.post("/autenticacion/salir")

    respuesta = client.post(
        "/autenticacion/ingresar",
        data={
            "email": REGISTRO["email"],
            "password": REGISTRO["password"],
        },
    )

    assert respuesta.status_code == 302
    assert respuesta.location.endswith("/panel")


def test_usuario_empresarial_autenticado_no_vuelve_a_estado(
    app,
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/autenticacion/ingresar")

    assert respuesta.status_code == 302
    assert respuesta.location.endswith("/panel")
