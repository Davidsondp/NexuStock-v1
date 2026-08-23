from decimal import Decimal

import pytest

from app.models import Bodega, Empresa, Inventario, Producto, Usuario, db
from app.services.contexto import ContextoOperacion
from app.services.inventario import ServicioInventario
from app.services.reportes import ErrorReporte, ServicioReportes, construir_periodo
from app.services.ventas import ServicioVentas
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        usuario.empresa.suscripcion_actual.plan.funciones = {
            **usuario.empresa.suscripcion_actual.plan.funciones,
            "analitica": True,
            "reportes.avanzados": True,
        }
        bodega = db.session.scalar(db.select(Bodega).where(Bodega.empresa_id == usuario.empresa_id))
        primero = Producto(
            empresa_id=usuario.empresa_id,
            codigo="R-1",
            nombre="Más vendido",
            costo_referencia=100,
            precio_venta=200,
            stock_maximo=100,
        )
        segundo = Producto(
            empresa_id=usuario.empresa_id,
            codigo="R-2",
            nombre="Sobrestock",
            costo_referencia=50,
            precio_venta=80,
            stock_maximo=5,
        )
        db.session.add_all([primero, segundo])
        db.session.commit()
        inventario = ServicioInventario(
            usuario, ContextoOperacion(usuario.empresa_id, bodega.sucursal, bodega)
        )
        inventario.entrada(producto_id=primero.id, cantidad=20, costo_unitario=100, motivo="Carga")
        inventario.entrada(producto_id=segundo.id, cantidad=10, costo_unitario=50, motivo="Carga")
        venta = ServicioVentas(usuario).crear(
            numero="R-VTA",
            bodega_id=bodega.id,
            items=[
                {"producto_id": primero.id, "cantidad": 5, "precio_unitario": 200, "impuesto": 190}
            ],
        )
        ServicioVentas(usuario).reservar(venta.id)
        ServicioVentas(usuario).confirmar(venta.id)
        return usuario.id, bodega.id, primero.id, segundo.id


def test_reporte_stock_calcula_valor_actual(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        filas = ServicioReportes(db.session.get(Usuario, ids[0])).stock()
        valores = {p.id: Decimal(i.cantidad) * Decimal(i.costo_promedio) for i, p, _ in filas}
        assert valores[ids[2]] == 1500 and valores[ids[3]] == 500


def test_analitica_calcula_ventas_costo_margen_y_valor(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        datos = ServicioReportes(db.session.get(Usuario, ids[0])).analitica(construir_periodo())
        assert datos["ventas_confirmadas"] == 1
        assert Decimal(datos["ingresos"]) == 1190
        assert Decimal(datos["costo_ventas"]) == 500
        assert Decimal(datos["margen_bruto"]) == 690
        assert Decimal(datos["valor_inventario_actual"]) == 2000
        assert datos["productos_mas_vendidos"][0]["producto_id"] == ids[2]


def test_sobrestock_y_sin_movimiento_se_derivan_sin_guardar_resumen(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        datos = ServicioReportes(db.session.get(Usuario, ids[0])).analitica(construir_periodo())
        assert {f["producto_id"] for f in datos["sobrestock"]} == {ids[3]}
        assert isinstance(datos["productos_sin_movimiento"], list)


def test_dinero_dormido_valoriza_exceso_sin_duplicarlo(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        datos = ServicioReportes(db.session.get(Usuario, ids[0])).dinero_dormido(bodega_id=ids[1])
        assert Decimal(datos["monto"]) == 250
        assert Decimal(datos["unidades"]) == 5
        assert datos["productos"] == 1
        assert datos["detalle"][0]["causas"] == ["sobrestock"]


def test_periodo_invalido_es_rechazado(app):
    with app.app_context(), pytest.raises(ErrorReporte):
        construir_periodo("2026-08-12", "2026-08-01")
    with app.app_context(), pytest.raises(ErrorReporte):
        construir_periodo("2020-01-01", "2026-08-01")


def test_analitica_respeta_funcion_del_plan(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        usuario.empresa.suscripcion_actual.plan.funciones = {}
        db.session.commit()
        with pytest.raises(PermissionError):
            ServicioReportes(usuario).analitica(construir_periodo())


def test_no_consulta_bodega_ajena(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        otra = Empresa(nombre="Ajena", email="reporte-ajeno@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        from app.models import Sucursal

        sucursal = Sucursal(empresa_id=otra.id, codigo="AJ", nombre="Ajena")
        db.session.add(sucursal)
        db.session.flush()
        bodega = Bodega(empresa_id=otra.id, sucursal_id=sucursal.id, codigo="AJ", nombre="Ajena")
        db.session.add(bodega)
        db.session.commit()
        with pytest.raises(PermissionError):
            ServicioReportes(db.session.get(Usuario, ids[0])).stock(bodega_id=bodega.id)


def test_api_reportes_entrega_json_en_espanol(app, client):
    _preparar(app, client)
    stock = client.get("/api/reportes/stock")
    analitica = client.get("/api/reportes/analitica")
    assert stock.status_code == 200 and len(stock.get_json()["stock"]) == 2
    assert analitica.status_code == 200
    assert "valor_inventario_actual" in analitica.get_json()


def test_resumen_ejecutivo_exige_plan_y_calcula_indicadores(app, client):
    ids = _preparar(app, client)
    assert client.get("/api/reportes/resumen-ejecutivo").status_code == 403
    usuario = db.session.get(Usuario, ids[0])
    plan = usuario.empresa.suscripcion_actual.plan
    plan.funciones = {**plan.funciones, "dashboard.ejecutivo": True}
    db.session.commit()
    db.session.expire_all()
    respuesta = client.get("/api/reportes/resumen-ejecutivo")
    assert respuesta.status_code == 200, respuesta.get_json()
    assert Decimal(respuesta.get_json()["ticket_promedio"]) == 1190
    assert Decimal(respuesta.get_json()["margen_bruto_porcentaje"]) > 0
