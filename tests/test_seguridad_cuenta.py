from app.models import Usuario, db
from app.services.seguridad_cuenta import (
    codigo_totp,
    confirmar_2fa,
    confirmar_verificacion,
    emitir_verificacion,
    iniciar_2fa,
)
from tests.test_autenticacion import REGISTRO


def test_verificacion_correo_token_unico_y_expirable(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        token = emitir_verificacion(usuario, enviar=False)
        confirmar_verificacion(token)
        assert usuario.email_verificado
        assert usuario.token_verificacion_hash is None


def test_login_con_2fa_exige_codigo_antes_de_crear_sesion(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    client.post("/autenticacion/salir")
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        secreto = iniciar_2fa(usuario)
        confirmar_2fa(usuario, codigo_totp(secreto))
    respuesta = client.post(
        "/autenticacion/ingresar",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/autenticacion/segundo-factor")
    assert client.get("/panel").status_code == 302
    confirmado = client.post("/autenticacion/segundo-factor", data={"codigo": codigo_totp(secreto)})
    assert confirmado.status_code == 302
    assert confirmado.headers["Location"].endswith("/panel")
    assert client.get("/panel").status_code == 200


def test_codigo_2fa_incorrecto_no_autentica(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    client.post("/autenticacion/salir")
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        secreto = iniciar_2fa(usuario)
        confirmar_2fa(usuario, codigo_totp(secreto))
    client.post(
        "/autenticacion/ingresar",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )
    respuesta = client.post("/autenticacion/segundo-factor", data={"codigo": "000000"})
    assert respuesta.status_code == 200
    assert "inválido" in respuesta.get_data(as_text=True)


def test_2fa_no_registra_acceso_hasta_validar_codigo(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    client.post("/autenticacion/salir")
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        secreto = iniciar_2fa(usuario)
        confirmar_2fa(usuario, codigo_totp(secreto))
        usuario.ultimo_acceso = None
        db.session.commit()
    client.post(
        "/autenticacion/ingresar",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )
    with app.app_context():
        assert db.session.scalar(db.select(Usuario)).ultimo_acceso is None
    client.post("/autenticacion/segundo-factor", data={"codigo": codigo_totp(secreto)})
    with app.app_context():
        assert db.session.scalar(db.select(Usuario)).ultimo_acceso is not None
