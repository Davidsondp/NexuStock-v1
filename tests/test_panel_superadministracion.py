from app.models import Usuario, db

CORREO_SUPERADMIN = "panel.superadmin@nexustock.cl"
CLAVE_SUPERADMIN = "ClaveSuperAdmin123"


def crear_superadmin(app):
    with app.app_context():
        usuario = Usuario(
            empresa_id=None,
            nombre="Super",
            apellido="Administrador",
            email=CORREO_SUPERADMIN,
            rol="super_admin",
            activo=True,
        )
        usuario.set_password(CLAVE_SUPERADMIN)
        db.session.add(usuario)
        db.session.commit()


def iniciar_sesion_superadmin(client):
    return client.post(
        "/autenticacion/ingresar",
        data={
            "email": CORREO_SUPERADMIN,
            "password": CLAVE_SUPERADMIN,
        },
    )


def test_panel_exige_autenticacion(client):
    respuesta = client.get("/superadministracion")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_superadmin_es_redirigido_a_su_panel(app, client):
    crear_superadmin(app)

    respuesta = iniciar_sesion_superadmin(client)

    assert respuesta.status_code == 302
    assert respuesta.location.endswith("/superadministracion")


def test_superadmin_puede_ver_panel_global(app, client):
    crear_superadmin(app)
    iniciar_sesion_superadmin(client)

    respuesta = client.get("/superadministracion")

    assert respuesta.status_code == 200
    assert b"Panel global" in respuesta.data
    assert b"Empresas" in respuesta.data
    assert b"Planes" in respuesta.data
    assert b"Suscripciones" in respuesta.data
    assert b"Pagos" in respuesta.data
    assert "Auditoría".encode("utf-8") in respuesta.data


def test_superadmin_esta_aislado_del_panel_empresarial(app, client):
    crear_superadmin(app)
    iniciar_sesion_superadmin(client)

    assert client.get("/panel").status_code == 403
    assert client.get("/panel/productos").status_code == 403
    assert client.get("/api/productos").status_code == 403

    # El ámbito global permanece disponible exclusivamente en su panel.
    assert client.get("/superadministracion").status_code == 200
    assert client.get("/api/superadmin/resumen").status_code == 200


def test_usuario_empresarial_no_puede_ver_panel_global(app, client):
    from tests.test_autenticacion import REGISTRO

    client.post("/autenticacion/registro", data=REGISTRO)

    respuesta = client.get("/superadministracion")

    assert respuesta.status_code == 403


def test_superadmin_autenticado_no_vuelve_a_estado(app, client):
    crear_superadmin(app)
    iniciar_sesion_superadmin(client)

    respuesta = client.get("/autenticacion/ingresar")

    assert respuesta.status_code == 302
    assert respuesta.location.endswith("/superadministracion")
