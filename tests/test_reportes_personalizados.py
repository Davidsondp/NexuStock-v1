from datetime import timedelta

from app.models import Bodega, Inventario, Producto, SnapshotInventario, Usuario, db, utcnow
from app.services.reportes_personalizados import capturar_snapshot_inventario
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        usuario.empresa.suscripcion_actual.plan.funciones = {
            **usuario.empresa.suscripcion_actual.plan.funciones,
            "reportes.personalizados": True,
            "analitica": True,
        }
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="RP-1",
            nombre="Reporte",
            costo_referencia=1,
            precio_venta=2,
        )
        db.session.add(producto)
        db.session.flush()
        bodega = db.session.scalar(db.select(Bodega))
        db.session.add(
            Inventario(
                empresa_id=usuario.empresa_id,
                producto_id=producto.id,
                bodega_id=bodega.id,
                cantidad=10,
                cantidad_reservada=0,
                costo_promedio=1,
            )
        )
        db.session.commit()


def test_reporte_personalizado_crea_ejecuta_elimina(app, client):
    _preparar(app, client)
    creado = client.post(
        "/api/reportes-personalizados",
        json={"nombre": "Stock diario", "tipo": "stock", "configuracion": {}},
    )
    assert creado.status_code == 201
    reporte_id = creado.get_json()["id"]
    ejecucion = client.get(f"/api/reportes-personalizados/{reporte_id}/ejecutar")
    assert ejecucion.status_code == 200
    assert ejecucion.get_json()["datos"][0]["cantidad"] == "10.000"
    assert client.delete(f"/api/reportes-personalizados/{reporte_id}").status_code == 204


def test_snapshot_diario_es_idempotente_y_alimenta_analitica(app, client):
    _preparar(app, client)
    with app.app_context():
        assert capturar_snapshot_inventario() == 1
        assert capturar_snapshot_inventario() == 0
        assert db.session.scalar(db.select(db.func.count(SnapshotInventario.id))) == 1
    desde = (utcnow().date() - timedelta(days=1)).isoformat()
    respuesta = client.get(f"/api/reportes/analitica?desde={desde}")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["dias_con_snapshot"] == 1
    assert respuesta.get_json()["inventario_promedio"] == "10.00"
