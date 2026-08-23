from app.models import Producto, ProductoImagen, Usuario, db
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="IMG-1",
            nombre="Con imágenes",
            costo_referencia=1,
            precio_venta=2,
        )
        db.session.add(producto)
        db.session.commit()
        return producto.id


def test_ciclo_imagenes_producto_y_principal(app, client):
    producto_id = _preparar(app, client)
    primera = client.post(
        f"/api/productos/{producto_id}/imagenes",
        json={"url": "https://cdn.ejemplo.cl/uno.webp"},
    )
    segunda = client.post(
        f"/api/productos/{producto_id}/imagenes",
        json={"url": "https://cdn.ejemplo.cl/dos.png"},
    )
    assert primera.status_code == segunda.status_code == 201
    assert primera.get_json()["es_principal"]
    imagen_id = segunda.get_json()["id"]
    assert (
        client.post(f"/api/productos/{producto_id}/imagenes/{imagen_id}/principal").status_code
        == 200
    )
    listado = client.get(f"/api/productos/{producto_id}/imagenes").get_json()
    assert sum(i["es_principal"] for i in listado["imagenes"]) == 1
    assert client.delete(f"/api/productos/{producto_id}/imagenes/{imagen_id}").status_code == 204
    with app.app_context():
        restante = db.session.scalar(db.select(ProductoImagen))
        assert restante.es_principal


def test_rechaza_url_insegura_y_empresa_ajena(app, client):
    producto_id = _preparar(app, client)
    respuesta = client.post(
        f"/api/productos/{producto_id}/imagenes", json={"url": "http://inseguro/uno.png"}
    )
    assert respuesta.status_code == 400
    assert client.get("/api/productos/99999/imagenes").status_code == 403


def test_panel_imagenes_producto(app, client):
    producto_id = _preparar(app, client)
    respuesta = client.get(f"/panel/productos/{producto_id}/imagenes")
    assert respuesta.status_code == 200
    assert "Imágenes de Con imágenes" in respuesta.get_data(as_text=True)
