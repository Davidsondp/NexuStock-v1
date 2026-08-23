from app.models import ClaveApi, Producto, Usuario, db
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        usuario.empresa.suscripcion_actual.plan.funciones = {
            **usuario.empresa.suscripcion_actual.plan.funciones,
            "api": True,
        }
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="API-1",
            nombre="Producto API",
            costo_referencia=1,
            precio_venta=2,
        )
        db.session.add(producto)
        db.session.commit()


def test_token_se_muestra_una_vez_y_autentica_api_v1(app, client):
    _preparar(app, client)
    creada = client.post(
        "/api/claves", json={"nombre": "Integración", "permisos": ["productos:leer"]}
    )
    assert creada.status_code == 201
    token = creada.get_json()["token"]
    listado = client.get("/api/claves").get_json()["claves"]
    assert "token" not in listado[0]
    respuesta = client.get("/api/v1/productos", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["datos"][0]["codigo"] == "API-1"
    with app.app_context():
        clave = db.session.scalar(db.select(ClaveApi))
        assert clave.ultimo_uso is not None
        assert token not in clave.secreto_hash


def test_revocacion_y_scope_bloquean_api(app, client):
    _preparar(app, client)
    creada = client.post(
        "/api/claves", json={"nombre": "Stock", "permisos": ["stock:leer"]}
    ).get_json()
    token = creada["token"]
    assert (
        client.get("/api/v1/productos", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )
    assert client.delete(f"/api/claves/{creada['id']}").status_code == 200


def test_plan_sin_api_no_administra_claves(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    assert client.get("/api/claves").status_code == 403
