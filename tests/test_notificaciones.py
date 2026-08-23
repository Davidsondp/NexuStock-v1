from app.models import Bodega, Inventario, Notificacion, Producto, Usuario, db
from app.services.alertas import ServicioAlertas
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        bodega = db.session.scalar(db.select(Bodega))
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="NOT-1",
            nombre="Notificable",
            costo_referencia=1,
            precio_venta=2,
            stock_minimo=5,
            punto_reorden=0,
        )
        db.session.add(producto)
        db.session.flush()
        db.session.add(
            Inventario(
                empresa_id=usuario.empresa_id,
                producto_id=producto.id,
                bodega_id=bodega.id,
                cantidad=1,
                cantidad_reservada=0,
                costo_promedio=1,
            )
        )
        db.session.commit()
        ServicioAlertas(usuario).generar()
        return usuario.id


def test_alerta_crea_notificacion_sin_duplicar(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        cantidad = db.session.scalar(db.select(db.func.count(Notificacion.id)))
        ServicioAlertas(db.session.get(Usuario, usuario_id)).generar()
        assert db.session.scalar(db.select(db.func.count(Notificacion.id))) == cantidad
    respuesta = client.get("/api/notificaciones")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["no_leidas"] == cantidad
    notificacion_id = respuesta.get_json()["notificaciones"][0]["id"]
    assert client.post(f"/api/notificaciones/{notificacion_id}/leer").status_code == 200
    assert client.post("/api/notificaciones/leer-todas").status_code == 200
    assert client.get("/api/notificaciones?solo_no_leidas=true").get_json()["no_leidas"] == 0
