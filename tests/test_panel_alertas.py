from pathlib import Path

from app.models import Usuario, db
from tests.test_autenticacion import REGISTRO


def registrar_empresa(client):
    return client.post(
        "/autenticacion/registro",
        data=REGISTRO,
    )


def test_panel_alertas_exige_autenticacion(
    client,
):
    respuesta = client.get("/panel/alertas")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_panel_alertas_expone_interfaz_empresarial(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/alertas")

    assert respuesta.status_code == 200
    assert "Centro de alertas".encode("utf-8") in respuesta.data

    textos_unicode = (
        "Navegación empresarial",
        "Operación",
        "Cerrar sesión",
        "Control automático",
        "automáticamente",
        "Prioridad crítica",
        "Recomendación de compra",
    )

    for texto_unicode in textos_unicode:
        assert texto_unicode.encode("utf-8") in respuesta.data
    assert b'data-api-alertas="/api/alertas"' in respuesta.data
    assert b'class="principal"' in respuesta.data
    assert b'class="cabecera__grupo"' in respuesta.data
    assert b'id="cerrar-menu"' in respuesta.data
    assert b'class="superposicion"' in respuesta.data
    assert b'id="fondo-menu"' not in respuesta.data
    assert b'<section class="contenido">' not in respuesta.data
    assert b'id="lista-alertas"' in respuesta.data
    assert b'id="filtro-estado-alertas"' in respuesta.data
    assert b'id="filtro-tipo-alertas"' in respuesta.data
    assert b'id="resumen-alertas-activas"' in respuesta.data
    assert b'id="resumen-alertas-criticas"' in respuesta.data
    assert b'id="resumen-alertas-altas"' in respuesta.data
    assert b"js/alertas.js" in respuesta.data
    assert b"css/alertas.css" in respuesta.data
    assert b'name="csrf_token"' in respuesta.data


def test_admin_puede_gestionar_alertas(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/alertas")

    assert respuesta.status_code == 200
    assert b'data-permiso-gestionar="true"' in respuesta.data


def test_empleado_solo_consulta_alertas(
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

    respuesta = client.get("/panel/alertas")

    assert respuesta.status_code == 200
    assert b'data-permiso-gestionar="false"' in respuesta.data


def test_superadmin_no_accede_alertas_empresariales(
    app,
    client,
):
    with app.app_context():
        usuario = Usuario(
            empresa_id=None,
            nombre="Super",
            apellido="Alertas",
            email=("super.alertas" "@nexustock.cl"),
            rol="super_admin",
            activo=True,
        )
        usuario.set_password("ClaveSuperAdmin123")
        db.session.add(usuario)
        db.session.commit()

    client.post(
        "/autenticacion/ingresar",
        data={
            "email": "super.alertas@nexustock.cl",
            "password": "ClaveSuperAdmin123",
        },
    )

    respuesta = client.get("/panel/alertas")

    assert respuesta.status_code == 403


def test_panel_enlaza_centro_alertas(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    assert b"/panel/alertas" in respuesta.data
    assert b'href="/api/alertas"' not in respuesta.data


def test_javascript_alertas_integra_acciones():
    contenido = Path("app/static/js/alertas.js").read_text(encoding="utf-8-sig")

    contratos = (
        "/resolver",
        "/ignorar",
        "X-CSRFToken",
        "permisoGestionar",
        "filtro-estado-alertas",
        "filtro-tipo-alertas",
        "lista-alertas",
    )

    for contrato in contratos:
        assert contrato in contenido
