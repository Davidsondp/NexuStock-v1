from app.models import LimiteSolicitud, Usuario, db
from tests.test_autenticacion import REGISTRO


def test_cabeceras_seguras_y_id_solicitud(app, client):
    respuesta = client.get("/estado", headers={"X-Request-ID": "solicitud-123"})
    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"
    assert respuesta.headers["X-Frame-Options"] == "DENY"
    assert respuesta.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=(self)" in respuesta.headers["Permissions-Policy"]
    assert "geolocation=(self)" in respuesta.headers["Permissions-Policy"]
    assert "microphone=()" in respuesta.headers["Permissions-Policy"]
    assert "frame-ancestors 'none'" in respuesta.headers["Content-Security-Policy"]
    assert "img-src 'self' https: data:" in respuesta.headers["Content-Security-Policy"]
    assert respuesta.headers["X-Request-ID"] == "solicitud-123"
    assert respuesta.headers["Cache-Control"] == "no-store"


def test_id_solicitud_invalido_no_se_refleja(app, client):
    respuesta = client.get(
        "/api/ruta-inexistente", headers={"X-Request-ID": "<script>alert(1)</script>"}
    )
    assert respuesta.headers["X-Request-ID"] != "<script>alert(1)</script>"
    assert len(respuesta.headers["X-Request-ID"]) == 32


def test_api_exige_json_en_operaciones_con_cuerpo(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    respuesta = client.post(
        "/api/productos", data="nombre=Producto", content_type="application/x-www-form-urlencoded"
    )
    assert respuesta.status_code == 415
    assert respuesta.get_json()["codigo"] == "tipo_contenido_no_admitido"


def test_json_malformado_genera_error_generico(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    respuesta = client.post("/api/productos", data=b'{"nombre":', content_type="application/json")
    assert respuesta.status_code == 400
    assert respuesta.get_json()["codigo"] == "solicitud_invalida"
    assert "traceback" not in respuesta.get_data(as_text=True).lower()


def test_errores_404_y_405_no_filtran_detalles(app, client):
    no_encontrado = client.get("/api/no-existe")
    metodo = client.put("/estado")
    assert (
        no_encontrado.status_code == 404 and no_encontrado.get_json()["codigo"] == "no_encontrado"
    )
    assert metodo.status_code == 405 and metodo.get_json()["codigo"] == "metodo_no_permitido"
    assert "werkzeug" not in no_encontrado.get_data(as_text=True).lower()


def test_limite_login_es_persistente_y_no_guarda_ip(app, client):
    for _ in range(10):
        respuesta = client.post(
            "/autenticacion/ingresar",
            data={"email": "nadie@nexustock.cl", "password": "incorrecta"},
        )
        assert respuesta.status_code == 200
    bloqueada = client.post(
        "/autenticacion/ingresar", data={"email": "nadie@nexustock.cl", "password": "incorrecta"}
    )
    assert bloqueada.status_code == 429
    assert int(bloqueada.headers["Retry-After"]) > 0
    with app.app_context():
        contador = db.session.scalar(db.select(LimiteSolicitud))
        assert contador.cantidad == 11 and len(contador.clave_hash) == 64
        assert "127.0.0.1" not in contador.clave_hash


def test_registro_compatible_comparte_limite_canonico(
    app,
    client,
):
    for _ in range(5):
        client.post(
            "/autenticacion/registro",
            data={},
        )

    bloqueada = client.post(
        "/registro",
        data={},
    )

    assert bloqueada.status_code == 429

    with app.app_context():
        contadores = list(
            db.session.scalars(
                db.select(LimiteSolicitud).where(LimiteSolicitud.ruta == "/autenticacion/registro")
            )
        )

        assert len(contadores) == 1
        assert contadores[0].cantidad == 6


def test_solicitud_empresarial_tiene_limite_persistente(
    client,
):
    for _ in range(5):
        client.post(
            "/empresarial/solicitar",
            data={},
        )

    bloqueada = client.post(
        "/empresarial/solicitar",
        data={},
    )

    assert bloqueada.status_code == 429
    assert int(bloqueada.headers["Retry-After"]) > 0


def test_reenvio_verificacion_tiene_limite_persistente(
    client,
):
    for _ in range(5):
        client.post(
            "/autenticacion/reenviar-verificacion",
            data={
                "email": "inexistente@nexustock.cl",
            },
        )

    bloqueada = client.post(
        "/autenticacion/reenviar-verificacion",
        data={
            "email": "inexistente@nexustock.cl",
        },
    )

    assert bloqueada.status_code == 429
    assert int(bloqueada.headers["Retry-After"]) > 0


def test_cookie_de_sesion_tiene_atributos_defensivos(app, client):
    respuesta = client.post("/autenticacion/registro", data=REGISTRO)
    cookie = next(
        c for c in respuesta.headers.getlist("Set-Cookie") if c.startswith("nexustock_sesion=")
    )
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_csrf_bloquea_formulario_sin_token_cuando_esta_activo(app, client):
    app.config["WTF_CSRF_ENABLED"] = True
    respuesta = client.post("/autenticacion/registro", data=REGISTRO)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["codigo"] == "solicitud_invalida"


def test_payload_demasiado_grande_es_rechazado(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 32
    respuesta = client.post(
        "/api/productos", data=b'{"nombre":"' + b"x" * 100 + b'"}', content_type="application/json"
    )
    assert respuesta.status_code == 413
    assert respuesta.get_json()["codigo"] == "contenido_demasiado_grande"


def test_no_hay_webhook_financiero_generico(app, client):
    app.config["WTF_CSRF_ENABLED"] = True
    respuesta = client.post("/webhooks/pagos/webpay", data=b"{}", content_type="application/json")
    assert respuesta.status_code == 404
