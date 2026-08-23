def test_rutas_get_sin_parametros_no_generan_error_interno(app, client):
    """Toda pantalla o endpoint estático registrado debe responder sin 500."""
    fallas = []
    for regla in app.url_map.iter_rules():
        if regla.arguments or "GET" not in regla.methods or regla.endpoint == "static":
            continue
        respuesta = client.get(regla.rule)
        if respuesta.status_code >= 500:
            fallas.append((regla.rule, respuesta.status_code))

    assert fallas == []
