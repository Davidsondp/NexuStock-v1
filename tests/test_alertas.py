from datetime import timedelta
from decimal import Decimal

import pytest

from app.models import (
    AlertaInventario,
    Bodega,
    Empresa,
    Inventario,
    Movimiento,
    Producto,
    Usuario,
    db,
    utcnow,
)
from app.services.alertas import ErrorAlerta, ServicioAlertas
from app.services.contexto import ContextoOperacion
from app.services.inventario import ServicioInventario
from tests.test_autenticacion import REGISTRO


def _preparar(app, client, *, cantidad=2, minimo=5, reorden=8, maximo=20):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        bodega = db.session.scalar(db.select(Bodega).where(Bodega.empresa_id == usuario.empresa_id))
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="A-1",
            nombre="Producto alerta",
            costo_referencia=10,
            precio_venta=20,
            stock_minimo=minimo,
            punto_reorden=reorden,
            stock_maximo=maximo,
        )
        db.session.add(producto)
        db.session.commit()
        if cantidad:
            ServicioInventario(
                usuario, ContextoOperacion(usuario.empresa_id, bodega.sucursal, bodega)
            ).entrada(
                producto_id=producto.id,
                cantidad=cantidad,
                costo_unitario=10,
                motivo="Saldo inicial",
            )
        return usuario.id, bodega.id, producto.id


def test_genera_stock_bajo_y_recomendacion_sin_duplicar(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioAlertas(db.session.get(Usuario, ids[0]))
        primero = servicio.generar()
        segundo = servicio.generar()
        tipos = set(db.session.scalars(db.select(AlertaInventario.tipo)))
        assert primero.creadas == 2 and segundo.creadas == 0 and segundo.actualizadas == 2
        assert tipos == {"stock_bajo", "recomendacion_compra"}
        recomendacion = db.session.scalar(
            db.select(AlertaInventario).where(AlertaInventario.tipo == "recomendacion_compra")
        )
        assert Decimal(recomendacion.datos["cantidad_sugerida"]) == 18


def test_sobrestock_se_resuelve_al_normalizar_stock(app, client):
    ids = _preparar(app, client, cantidad=25, minimo=1, reorden=2, maximo=20)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        servicio = ServicioAlertas(usuario)
        servicio.generar()
        alerta = db.session.scalar(
            db.select(AlertaInventario).where(AlertaInventario.tipo == "sobrestock")
        )
        assert alerta.estado == "activa"
        inventario = db.session.scalar(db.select(Inventario))
        ServicioInventario(
            usuario,
            ContextoOperacion(usuario.empresa_id, inventario.bodega.sucursal, inventario.bodega),
        ).salida(producto_id=ids[2], cantidad=5, motivo="Normalización")
        resultado = servicio.generar()
        db.session.refresh(alerta)
        assert resultado.resueltas == 1 and alerta.estado == "resuelta"


def test_riesgo_agotamiento_usa_consumo_historico(app, client):
    ids = _preparar(app, client, cantidad=20, minimo=1, reorden=2, maximo=100)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        bodega = db.session.get(Bodega, ids[1])
        ServicioInventario(
            usuario, ContextoOperacion(usuario.empresa_id, bodega.sucursal, bodega)
        ).salida(producto_id=ids[2], cantidad=17, motivo="Venta histórica")
        ServicioAlertas(usuario).generar()
        alerta = db.session.scalar(
            db.select(AlertaInventario).where(AlertaInventario.tipo == "riesgo_agotamiento")
        )
        assert alerta and alerta.datos["ventana_dias"] == 30
        assert Decimal(alerta.datos["promedio_diario"]) == Decimal(17) / Decimal(30)


def test_producto_sin_movimiento_requiere_umbral_real(app, client):
    ids = _preparar(app, client, cantidad=0, minimo=0, reorden=0, maximo=20)
    with app.app_context():
        producto = db.session.get(Producto, ids[2])
        producto.creado_en = utcnow() - timedelta(days=100)
        db.session.add(
            Inventario(
                empresa_id=db.session.get(Usuario, ids[0]).empresa_id,
                bodega_id=ids[1],
                producto_id=ids[2],
                cantidad=3,
                cantidad_reservada=0,
                costo_promedio=10,
            )
        )
        db.session.commit()
        ServicioAlertas(db.session.get(Usuario, ids[0])).generar()
        assert (
            db.session.scalar(
                db.select(AlertaInventario).where(AlertaInventario.tipo == "sin_movimiento")
            )
            is not None
        )


def test_ignorar_conserva_historial_y_permite_nueva_alerta(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioAlertas(db.session.get(Usuario, ids[0]))
        servicio.generar()
        alerta = db.session.scalar(
            db.select(AlertaInventario).where(AlertaInventario.tipo == "stock_bajo")
        )
        servicio.cambiar_estado(alerta.id, "ignorada")
        servicio.generar()
        estados = list(
            db.session.scalars(
                db.select(AlertaInventario.estado)
                .where(AlertaInventario.tipo == "stock_bajo")
                .order_by(AlertaInventario.id)
            )
        )
        assert estados == ["ignorada", "activa"]


def test_no_gestiona_alerta_ajena(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        otra = Empresa(nombre="Ajena", email="alerta-ajena@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        producto = Producto(
            empresa_id=otra.id, codigo="AJ", nombre="Ajeno", costo_referencia=1, precio_venta=2
        )
        db.session.add(producto)
        db.session.flush()
        from app.models import Sucursal

        sucursal = Sucursal(empresa_id=otra.id, codigo="AJ", nombre="Ajena")
        db.session.add(sucursal)
        db.session.flush()
        bodega = Bodega(empresa_id=otra.id, sucursal_id=sucursal.id, codigo="AJ", nombre="Ajena")
        db.session.add(bodega)
        db.session.flush()
        alerta = AlertaInventario(
            empresa_id=otra.id,
            producto_id=producto.id,
            bodega_id=bodega.id,
            tipo="stock_bajo",
            titulo="Ajena",
            mensaje="Ajena",
        )
        db.session.add(alerta)
        db.session.commit()
        with pytest.raises(PermissionError):
            ServicioAlertas(db.session.get(Usuario, ids[0])).cambiar_estado(alerta.id, "resuelta")


def test_api_alertas_en_espanol(app, client):
    _preparar(app, client)
    generado = client.post("/api/alertas/generar")
    assert generado.status_code == 200 and generado.get_json()["creadas"] == 2
    listado = client.get("/api/alertas").get_json()["alertas"]
    assert {a["tipo"] for a in listado} == {"stock_bajo", "recomendacion_compra"}
