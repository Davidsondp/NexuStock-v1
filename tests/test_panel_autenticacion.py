from pathlib import Path


def test_ingreso_incluye_interfaz_visual(
    client,
):
    respuesta = client.get("/autenticacion/ingresar")

    assert respuesta.status_code == 200

    contratos = (
        b'id="autenticacion-pagina"',
        b'id="formulario-ingreso"',
        b'id="email"',
        b'id="password"',
        b'id="recordar"',
        b'id="alternar-password"',
        b'id="enlace-recuperacion"',
        b'id="enlace-registro"',
        b"css/autenticacion.css",
        b"js/autenticacion.js",
    )

    for contrato in contratos:
        assert contrato in respuesta.data

    textos = (
        "Bienvenido de nuevo",
        "Controla tu inventario con confianza",
        "Ingresar a NexuStock",
        "Olvidé mi contraseña",
    )

    for texto in textos:
        assert texto.encode("utf-8") in respuesta.data


def test_registro_incluye_interfaz_visual(
    client,
):
    respuesta = client.get("/autenticacion/registro")

    assert respuesta.status_code == 200

    contratos = (
        b'id="formulario-registro"',
        b'id="empresa_nombre"',
        b'id="rubro"',
        b'id="identificacion_fiscal"',
        b'id="nombre"',
        b'id="apellido"',
        b'id="email"',
        b'id="password"',
        b'id="confirmar_password"',
        b'id="alternar-password"',
        b'id="alternar-confirmacion"',
        b'id="enlace-ingreso"',
        b"css/autenticacion.css",
        b"js/autenticacion.js",
    )

    for contrato in contratos:
        assert contrato in respuesta.data

        textos = (
            "Prepara tu espacio de trabajo",
            "Completa cuatro pasos breves",
            "30 días gratis",
            "Ya tengo una cuenta",
        )

    for texto in textos:
        assert texto.encode("utf-8") in respuesta.data


def test_recuperacion_incluye_interfaz_visual(
    client,
):
    respuesta = client.get("/autenticacion/olvide-password")

    assert respuesta.status_code == 200

    contratos = (
        b'id="formulario-recuperacion"',
        b'id="email"',
        b'id="enlace-ingreso"',
        b"css/autenticacion.css",
        b"js/autenticacion.js",
    )

    for contrato in contratos:
        assert contrato in respuesta.data

    textos = (
        "Recuperar contraseña",
        "Te enviaremos instrucciones",
        "Volver a ingresar",
    )

    for texto in textos:
        assert texto.encode("utf-8") in respuesta.data


def test_restablecimiento_declara_interfaz_visual():
    contenido = Path("app/templates/autenticacion/" "restablecer_password.html").read_text(
        encoding="utf-8-sig"
    )

    contratos = (
        'id="formulario-restablecimiento"',
        'id="password"',
        'id="confirmar_password"',
        'id="alternar-password"',
        'id="alternar-confirmacion"',
    )

    for contrato in contratos:
        assert contrato in contenido


def test_javascript_autenticacion_controla_password():
    contenido = Path("app/static/js/autenticacion.js").read_text(encoding="utf-8-sig")

    contratos = (
        "alternar-password",
        "alternar-confirmacion",
        "aria-pressed",
        "X-CSRFToken",
    )

    for contrato in contratos:
        assert contrato in contenido


def test_formulario_rubros_conserva_unicode():
    contenido = Path("app/blueprints/autenticacion/forms.py").read_text(encoding="utf-8-sig")

    textos = (
        "Almacén",
        "Botillería",
        "Ferretería",
    )

    for texto in textos:
        assert texto in contenido
        mojibake = texto.encode("utf-8").decode("latin1")
        assert mojibake not in contenido
