from app.models import (
    Auditoria,
    Bodega,
    ConfiguracionEmpresa,
    Empresa,
    Sucursal,
    Suscripcion,
    Usuario,
    UsuarioSucursal,
    db,
)
from app.extensions import correo
from app.services.perfiles_empresa import capacidades_empresa

REGISTRO = {
    "empresa_nombre": "Almacén Central",
    "empresa_identificacion_fiscal": "76.123.456-0",
    "empresa_telefono": "+56223456789",
    "identificacion_fiscal": "12.345.678-5",
    "nombre": "Davidson",
    "apellido": "Pierre",
    "telefono": "+56952310902",
    "email": "admin@nexustock.cl",
    "password": "ClaveSegura123",
    "confirmar_password": "ClaveSegura123",
}


def test_registro_inicial_es_atomico_y_completo(app, client):
    respuesta = client.post("/autenticacion/registro", data=REGISTRO)
    assert respuesta.status_code == 302
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Empresa.id))) == 1
        assert db.session.scalar(db.select(db.func.count(Suscripcion.id))) == 1
        assert db.session.scalar(db.select(db.func.count(Sucursal.id))) == 1
        assert db.session.scalar(db.select(db.func.count(Bodega.id))) == 1
        assert db.session.scalar(db.select(db.func.count(Usuario.id))) == 1
        assert db.session.scalar(db.select(db.func.count(UsuarioSucursal.id))) == 1
        assert db.session.scalar(db.select(db.func.count(ConfiguracionEmpresa.id))) == 1
        assert db.session.scalar(db.select(db.func.count(Auditoria.id))) == 1
        usuario = db.session.scalar(db.select(Usuario))
        assert usuario.rol == "jefe"
        assert usuario.identificacion_fiscal == "12.345.678-5"
        assert usuario.empresa.identificacion_fiscal == "76.123.456-0"
        assert usuario.telefono != usuario.empresa.telefono
        assert usuario.check_password(REGISTRO["password"])


def test_registro_entrega_enlace_y_verificacion_habilita_ingreso(app, client):
    app.config["REQUIRE_EMAIL_VERIFICATION"] = True
    with correo.record_messages() as enviados:
        respuesta = client.post("/autenticacion/registro", data=REGISTRO)
        assert respuesta.status_code == 302
        assert len(enviados) == 1
        enlace = next(
            linea
            for linea in enviados[0].body.splitlines()
            if "/autenticacion/verificar-correo/" in linea
        )
    client.post("/autenticacion/salir")
    bloqueado = client.post(
        "/autenticacion/ingresar",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )
    assert bloqueado.status_code == 200
    assert b"verificar tu correo" in bloqueado.data
    assert client.get(enlace.split("localhost", 1)[1]).status_code == 302
    permitido = client.post(
        "/autenticacion/ingresar",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )
    assert permitido.status_code == 302


def test_correo_duplicado_no_crea_segunda_empresa(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    client.post("/autenticacion/salir")
    client.post("/autenticacion/registro", data={**REGISTRO, "empresa_nombre": "Otra"})
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Empresa.id))) == 1


def test_login_bloquea_tras_cinco_fallos(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    client.post("/autenticacion/salir")
    for _ in range(5):
        client.post(
            "/autenticacion/ingresar", data={"email": REGISTRO["email"], "password": "incorrecta"}
        )
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        assert usuario.intentos_fallidos == 5
        assert usuario.esta_bloqueado()


def test_login_correcto_reinicia_intentos(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    client.post("/autenticacion/salir")
    client.post(
        "/autenticacion/ingresar", data={"email": REGISTRO["email"], "password": "incorrecta"}
    )
    respuesta = client.post(
        "/autenticacion/ingresar",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )
    assert respuesta.status_code == 302
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        assert usuario.intentos_fallidos == 0
        assert usuario.ultimo_acceso is not None


def test_next_externo_no_se_usa(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    client.post("/autenticacion/salir")
    respuesta = client.post(
        "/autenticacion/ingresar?siguiente=https://malicioso.test",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )
    assert respuesta.location.endswith("/panel")


def test_paginas_autenticacion_cargan(client):
    assert client.get("/autenticacion/ingresar").status_code == 200
    assert client.get("/autenticacion/registro").status_code == 200


def test_solicitud_no_revela_si_correo_existe(app, client):
    conocida = client.post("/autenticacion/olvide-password", data={"email": "nadie@nexustock.cl"})
    client.post("/autenticacion/registro", data=REGISTRO)
    client.post("/autenticacion/salir")
    existente = client.post("/autenticacion/olvide-password", data={"email": REGISTRO["email"]})
    assert conocida.status_code == existente.status_code == 302
    assert conocida.location == existente.location


def test_token_es_de_un_solo_uso(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    client.post("/autenticacion/salir")
    with correo.record_messages() as enviados:
        client.post("/autenticacion/olvide-password", data={"email": REGISTRO["email"]})
        assert len(enviados) == 1
        enlace = [
            linea for linea in enviados[0].body.splitlines() if "/restablecer-password/" in linea
        ][0]
        ruta = enlace.split("localhost", 1)[1]
    respuesta = client.post(
        ruta, data={"password": "NuevaClave123", "confirmar_password": "NuevaClave123"}
    )
    assert respuesta.status_code == 302
    reutilizacion = client.get(ruta)
    assert reutilizacion.status_code == 302
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        assert usuario.check_password("NuevaClave123")
        assert usuario.token_restablecimiento_hash is None
        assert usuario.version_sesion == 2


def test_token_expirado_es_rechazado(app, client):
    from app.models import utcnow
    from datetime import timedelta

    client.post("/autenticacion/registro", data=REGISTRO)
    client.post("/autenticacion/salir")
    with correo.record_messages() as enviados:
        client.post("/autenticacion/olvide-password", data={"email": REGISTRO["email"]})
        enlace = [
            linea for linea in enviados[0].body.splitlines() if "/restablecer-password/" in linea
        ][0]
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        usuario.token_restablecimiento_expira = utcnow() - timedelta(seconds=1)
        db.session.commit()
    assert client.get(enlace.split("localhost", 1)[1]).status_code == 302


def test_cambio_password_invalida_otra_sesion(app, client):
    otro_navegador = app.test_client()
    client.post("/autenticacion/registro", data=REGISTRO)
    otro_navegador.post(
        "/autenticacion/ingresar",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )
    client.post("/autenticacion/salir")
    with correo.record_messages() as enviados:
        client.post("/autenticacion/olvide-password", data={"email": REGISTRO["email"]})
        enlace = [
            linea for linea in enviados[0].body.splitlines() if "/restablecer-password/" in linea
        ][0]
    client.post(
        enlace.split("localhost", 1)[1],
        data={"password": "NuevaClave123", "confirmar_password": "NuevaClave123"},
    )
    respuesta = otro_navegador.get("/autenticacion/ingresar")
    assert respuesta.status_code == 200
    assert b"Ingresar" in respuesta.data


def test_registro_muestra_selector_de_rubro(
    client,
):
    respuesta = client.get("/autenticacion/registro")

    assert respuesta.status_code == 200
    assert b'name="rubro"' in respuesta.data

    opciones = {
        "general",
        "almacen",
        "minimarket",
        "botilleria",
        "ferreteria",
        "farmacia",
    }

    for rubro in opciones:
        assert f'value="{rubro}"'.encode() in respuesta.data


def test_registro_farmacia_activa_capacidad(
    app,
    client,
):
    respuesta = client.post(
        "/autenticacion/registro",
        data={
            **REGISTRO,
            "rubro": "farmacia",
        },
    )

    assert respuesta.status_code == 302

    with app.app_context():
        configuracion = db.session.scalar(db.select(ConfiguracionEmpresa))

        assert configuracion is not None
        assert configuracion.opciones["rubro"] == "farmacia"

        capacidades = capacidades_empresa(configuracion.empresa)

        assert capacidades["inventario_farmaceutico"] is True


def test_registro_botilleria_no_activa_farmacia(
    app,
    client,
):
    respuesta = client.post(
        "/autenticacion/registro",
        data={
            **REGISTRO,
            "empresa_nombre": "Botillería Central",
            "identificacion_fiscal": "77.123.456-9",
            "email": "admin@botilleria.cl",
            "rubro": "botilleria",
        },
    )

    assert respuesta.status_code == 302

    with app.app_context():
        configuracion = db.session.scalar(db.select(ConfiguracionEmpresa))

        capacidades = capacidades_empresa(configuracion.empresa)

        assert configuracion.opciones["rubro"] == "botilleria"
        assert capacidades["inventario_farmaceutico"] is False


def test_registro_rechaza_rubro_desconocido(
    app,
    client,
):
    respuesta = client.post(
        "/autenticacion/registro",
        data={
            **REGISTRO,
            "rubro": "rubro_inventado",
        },
    )

    assert respuesta.status_code == 200

    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Empresa.id))) == 0


def test_registro_sin_rubro_conserva_general(
    app,
    client,
):
    respuesta = client.post(
        "/autenticacion/registro",
        data=REGISTRO,
    )

    assert respuesta.status_code == 302

    with app.app_context():
        configuracion = db.session.scalar(db.select(ConfiguracionEmpresa))

        assert configuracion.opciones["rubro"] == "general"


def test_raiz_muestra_portada_publica_con_ingreso_y_registro(
    client,
):
    respuesta = client.get("/")

    assert respuesta.status_code == 200
    assert b"/autenticacion/ingresar" in respuesta.data
    assert b"/autenticacion/registro" in respuesta.data
    assert "Controla tu inventario".encode("utf-8") in respuesta.data


def test_urls_historicas_de_autenticacion_siguen_funcionando(client):
    assert client.get("/login").status_code == 200
    assert client.get("/registro").status_code == 200

    respuesta = client.post("/registro", data=REGISTRO)
    assert respuesta.status_code == 302
    assert respuesta.location.endswith("/panel")


def test_raiz_redirige_empresa_al_panel(
    client,
):
    client.post(
        "/autenticacion/registro",
        data=REGISTRO,
    )

    respuesta = client.get("/")

    assert respuesta.status_code == 302
    assert respuesta.location.endswith("/panel")


def test_raiz_redirige_superadmin_a_panel_global(
    app,
    client,
):
    with app.app_context():
        usuario = Usuario(
            empresa_id=None,
            nombre="Super",
            apellido="Administrador",
            email="raiz.superadmin@nexustock.cl",
            rol="super_admin",
            activo=True,
        )
        usuario.set_password("ClaveSuperAdmin123")

        db.session.add(usuario)
        db.session.commit()

    ingreso = client.post(
        "/autenticacion/ingresar",
        data={
            "email": "raiz.superadmin@nexustock.cl",
            "password": "ClaveSuperAdmin123",
        },
    )

    assert ingreso.status_code == 302

    respuesta = client.get("/")

    assert respuesta.status_code == 302
    assert respuesta.location.endswith("/superadministracion")
