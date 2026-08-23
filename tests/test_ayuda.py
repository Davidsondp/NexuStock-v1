from app.extensions import correo
from app.models import Auditoria, db
from tests.test_autenticacion import REGISTRO

SOLICITUD = {
    "categoria": "inventario",
    "asunto": "No encuentro un movimiento",
    "mensaje": "Necesito ayuda para encontrar una entrada registrada ayer.",
    "pagina": "https://nexustock.cl/panel/inventario",
}


def test_centro_ayuda_exige_login_y_muestra_correo(client):
    assert client.get("/panel/ayuda").status_code == 302
    client.post("/autenticacion/registro", data=REGISTRO)
    respuesta = client.get("/panel/ayuda")
    assert respuesta.status_code == 200
    assert b"Centro de Ayuda" in respuesta.data
    assert b"equipos@nexustock.cl" in respuesta.data


def test_solicitud_envia_correo_y_audita_sin_guardar_mensaje(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with correo.record_messages() as enviados:
        respuesta = client.post("/ayuda/contacto", json=SOLICITUD)
        assert respuesta.status_code == 200
        assert respuesta.get_json()["enviado"] is True
        assert len(enviados) == 1
        assert enviados[0].recipients == ["equipos@nexustock.cl"]
        assert enviados[0].reply_to == REGISTRO["email"]
    with app.app_context():
        auditoria = db.session.scalar(
            db.select(Auditoria).where(Auditoria.accion == "soporte.solicitud")
        )
        assert auditoria.descripcion == SOLICITUD["asunto"]
        assert SOLICITUD["mensaje"] not in str(auditoria.datos_nuevos)


def test_contacto_valida_categoria_y_longitud(client):
    client.post("/autenticacion/registro", data=REGISTRO)
    respuesta = client.post(
        "/ayuda/contacto",
        json={"categoria": "desconocida", "asunto": "Ayuda", "mensaje": "muy corto"},
    )
    assert respuesta.status_code == 400


def test_falla_smtp_ofrece_correo_alternativo(app, client, monkeypatch):
    client.post("/autenticacion/registro", data=REGISTRO)

    def fallar(_mensaje):
        raise OSError("SMTP no disponible")

    monkeypatch.setattr("app.services.ayuda.correo.send", fallar)
    respuesta = client.post("/ayuda/contacto", json=SOLICITUD)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "correo": "equipos@nexustock.cl",
        "enviado": False,
    }


def test_limite_antispam_por_usuario(client):
    client.post("/autenticacion/registro", data=REGISTRO)
    for indice in range(5):
        datos = {**SOLICITUD, "asunto": f"Solicitud válida número {indice}"}
        assert client.post("/ayuda/contacto", json=datos).status_code == 200
    bloqueada = client.post("/ayuda/contacto", json=SOLICITUD)
    assert bloqueada.status_code == 400
    assert "límite" in bloqueada.get_json()["mensaje"]
