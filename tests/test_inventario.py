from decimal import Decimal

import pytest

from app.models import Auditoria, Empresa, Inventario, Movimiento, Producto, Usuario, db
from app.services.contexto import obtener_contexto
from app.services.inventario import (
    ErrorInventario,
    LimiteMovimientosAlcanzado,
    ServicioInventario,
    StockInsuficiente,
)
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.test_request_context():
        usuario = db.session.scalar(db.select(Usuario))
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="P-001",
            nombre="Producto",
            costo_referencia=100,
            precio_venta=200,
        )
        db.session.add(producto)
        db.session.commit()
        contexto = obtener_contexto(usuario)
        return usuario.id, producto.id, contexto.sucursal.id, contexto.bodega.id


def _servicio(ids):
    from app.services.contexto import ContextoOperacion
    from app.models import Sucursal, Bodega

    usuario = db.session.get(Usuario, ids[0])
    contexto = ContextoOperacion(
        usuario.empresa_id, db.session.get(Sucursal, ids[2]), db.session.get(Bodega, ids[3])
    )
    return ServicioInventario(usuario, contexto)


def test_entrada_crea_saldo_movimiento_y_auditoria(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        resultado = _servicio(ids).entrada(
            producto_id=ids[1], cantidad=10, costo_unitario=100, motivo="Compra inicial"
        )
        assert resultado.stock_anterior == 0
        assert resultado.stock_nuevo == 10
        assert resultado.costo_promedio == 100
        movimiento = db.session.get(Movimiento, resultado.movimiento_id)
        assert movimiento.stock_nuevo == movimiento.stock_anterior + movimiento.cantidad
        assert (
            db.session.scalar(
                db.select(db.func.count(Auditoria.id)).where(
                    Auditoria.accion == "inventario.entrada"
                )
            )
            == 1
        )


def test_costo_promedio_ponderado(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = _servicio(ids)
        servicio.entrada(producto_id=ids[1], cantidad=10, costo_unitario=100, motivo="Primera")
        resultado = _servicio(ids).entrada(
            producto_id=ids[1], cantidad=10, costo_unitario=200, motivo="Segunda"
        )
        assert resultado.stock_nuevo == 20
        assert resultado.costo_promedio == Decimal("150.0000")


def test_salida_no_permite_consumir_stock_reservado(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        _servicio(ids).entrada(
            producto_id=ids[1], cantidad=10, costo_unitario=100, motivo="Entrada"
        )
        inventario = db.session.scalar(db.select(Inventario))
        inventario.cantidad_reservada = 4
        db.session.commit()
        with pytest.raises(StockInsuficiente):
            _servicio(ids).salida(producto_id=ids[1], cantidad=7, motivo="Venta")
        inventario = db.session.scalar(db.select(Inventario))
        assert inventario.cantidad == 10
        assert db.session.scalar(db.select(db.func.count(Movimiento.id))) == 1


def test_ajuste_registra_delta_correcto(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        _servicio(ids).entrada(
            producto_id=ids[1], cantidad=10, costo_unitario=100, motivo="Entrada"
        )
        resultado = _servicio(ids).ajuste(producto_id=ids[1], stock_final=7, motivo="Conteo físico")
        movimiento = db.session.get(Movimiento, resultado.movimiento_id)
        assert movimiento.tipo == "ajuste"
        assert movimiento.cantidad == -3
        assert resultado.stock_nuevo == 7


def test_devolucion_incrementa_stock(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        _servicio(ids).entrada(producto_id=ids[1], cantidad=5, costo_unitario=100, motivo="Entrada")
        resultado = _servicio(ids).devolucion(
            producto_id=ids[1], cantidad=2, costo_unitario=100, motivo="Devolución cliente"
        )
        assert resultado.stock_nuevo == 7


def test_rechaza_cantidad_no_positiva(app, client):
    ids = _preparar(app, client)
    with app.app_context(), pytest.raises(ErrorInventario):
        _servicio(ids).entrada(
            producto_id=ids[1], cantidad=-1, costo_unitario=100, motivo="Inválida"
        )


def test_producto_de_otra_empresa_no_es_accesible(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        otra = Empresa(nombre="Otra", email="otra-inventario@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        ajeno = Producto(
            empresa_id=otra.id, codigo="AJENO", nombre="Ajeno", costo_referencia=1, precio_venta=2
        )
        db.session.add(ajeno)
        db.session.commit()
        ajeno_id = ajeno.id
        with pytest.raises(PermissionError):
            _servicio(ids).entrada(
                producto_id=ajeno_id, cantidad=1, costo_unitario=1, motivo="Intento cruzado"
            )
        assert (
            db.session.scalar(
                db.select(db.func.count(Inventario.id)).where(Inventario.producto_id == ajeno_id)
            )
            == 0
        )


def test_limite_mensual_se_aplica_antes_de_mutar(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        usuario.empresa.suscripcion_actual.plan.limite_movimientos_mes = 1
        db.session.commit()
        _servicio(ids).entrada(producto_id=ids[1], cantidad=2, costo_unitario=100, motivo="Primera")
        with pytest.raises(LimiteMovimientosAlcanzado):
            _servicio(ids).salida(producto_id=ids[1], cantidad=1, motivo="Segunda")
        assert db.session.scalar(db.select(Inventario.cantidad)) == 2


def test_movimiento_es_inmutable(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        resultado = _servicio(ids).entrada(
            producto_id=ids[1], cantidad=2, costo_unitario=100, motivo="Entrada"
        )
        movimiento = db.session.get(Movimiento, resultado.movimiento_id)
        movimiento.motivo = "Manipulado"
        with pytest.raises(ValueError):
            db.session.commit()
        db.session.rollback()


def test_api_movimientos_exige_autenticacion(client):
    respuesta = client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "entrada",
            "producto_id": 1,
            "cantidad": 1,
            "costo_unitario": 100,
            "motivo": "Prueba",
        },
    )

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_api_registra_entrada_salida_y_ajuste(
    app,
    client,
):
    ids = _preparar(app, client)

    entrada = client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "entrada",
            "producto_id": ids[1],
            "cantidad": 10,
            "costo_unitario": 125,
            "motivo": "Ingreso manual",
        },
    )

    assert entrada.status_code == 201

    movimiento_entrada = entrada.get_json()

    assert movimiento_entrada["tipo"] == "entrada"
    assert movimiento_entrada["stock_anterior"] == "0.000"
    assert movimiento_entrada["stock_nuevo"] == "10.000"
    assert movimiento_entrada["costo_promedio"] == "125.0000"

    salida = client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "salida",
            "producto_id": ids[1],
            "cantidad": 3,
            "precio_unitario": 250,
            "motivo": "Merma controlada",
        },
    )

    assert salida.status_code == 201
    assert salida.get_json()["stock_nuevo"] == "7.000"

    ajuste = client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "ajuste",
            "producto_id": ids[1],
            "stock_final": 6,
            "motivo": "Conteo físico",
        },
    )

    assert ajuste.status_code == 201
    assert ajuste.get_json()["stock_nuevo"] == "6.000"

    reporte = client.get(f"/api/reportes/stock?bodega_id={ids[3]}")

    assert reporte.status_code == 200

    fila = next(item for item in reporte.get_json()["stock"] if item["producto_id"] == ids[1])

    assert fila["cantidad"] == "6.000"


def test_api_registra_devolucion(
    app,
    client,
):
    ids = _preparar(app, client)

    client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "entrada",
            "producto_id": ids[1],
            "cantidad": 5,
            "costo_unitario": 100,
            "motivo": "Ingreso inicial",
        },
    )

    devolucion = client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "devolucion",
            "producto_id": ids[1],
            "cantidad": 2,
            "costo_unitario": 100,
            "motivo": "Devolución del cliente",
        },
    )

    assert devolucion.status_code == 201
    assert devolucion.get_json()["tipo"] == "devolucion"
    assert devolucion.get_json()["stock_nuevo"] == "7.000"


def test_api_rechaza_tipo_y_stock_invalido(
    app,
    client,
):
    ids = _preparar(app, client)

    tipo_invalido = client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "inventado",
            "producto_id": ids[1],
            "cantidad": 1,
            "motivo": "No permitido",
        },
    )

    assert tipo_invalido.status_code == 400
    assert tipo_invalido.get_json()["codigo"] == "movimiento_invalido"

    stock_insuficiente = client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "salida",
            "producto_id": ids[1],
            "cantidad": 5,
            "motivo": "Salida imposible",
        },
    )

    assert stock_insuficiente.status_code == 400
    assert stock_insuficiente.get_json()["codigo"] == "stock_insuficiente"


def test_api_lista_stock_operativo(
    app,
    client,
):
    ids = _preparar(app, client)

    entrada = client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "entrada",
            "producto_id": ids[1],
            "cantidad": 8,
            "costo_unitario": 150,
            "motivo": "Carga para panel",
        },
    )

    assert entrada.status_code == 201

    respuesta = client.get("/api/inventario/stock")

    assert respuesta.status_code == 200

    datos = respuesta.get_json()

    assert "stock" in datos
    assert datos["bodega_id"] == ids[3]

    fila = next(item for item in datos["stock"] if item["producto_id"] == ids[1])

    campos = {
        "inventario_id",
        "producto_id",
        "producto_codigo",
        "producto_nombre",
        "bodega_id",
        "bodega_nombre",
        "cantidad",
        "reservada",
        "disponible",
        "costo_promedio",
        "valor",
    }

    assert campos.issubset(fila)
    assert fila["cantidad"] == "8.000"
    assert fila["reservada"] == "0.000"
    assert fila["disponible"] == "8.000"
    assert fila["costo_promedio"] == "150.0000"
    assert fila["valor"] == "1200.00"


def test_api_lista_movimientos_operativos(
    app,
    client,
):
    ids = _preparar(app, client)

    entrada = client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "entrada",
            "producto_id": ids[1],
            "cantidad": 4,
            "costo_unitario": 200,
            "motivo": "Movimiento visible",
        },
    )

    assert entrada.status_code == 201

    respuesta = client.get("/api/inventario/movimientos")

    assert respuesta.status_code == 200

    datos = respuesta.get_json()

    assert "movimientos" in datos
    assert datos["bodega_id"] == ids[3]

    movimiento = datos["movimientos"][0]

    campos = {
        "id",
        "producto_id",
        "producto_codigo",
        "producto_nombre",
        "bodega_id",
        "tipo",
        "cantidad",
        "stock_anterior",
        "stock_nuevo",
        "costo_unitario",
        "precio_unitario",
        "motivo",
        "fecha",
    }

    assert campos.issubset(movimiento)
    assert movimiento["producto_id"] == ids[1]
    assert movimiento["tipo"] == "entrada"
    assert movimiento["cantidad"] == "4.000"
    assert movimiento["stock_anterior"] == "0.000"
    assert movimiento["stock_nuevo"] == "4.000"
    assert movimiento["motivo"] == "Movimiento visible"


def test_api_movimientos_limita_resultados(
    app,
    client,
):
    ids = _preparar(app, client)

    for numero in range(3):
        respuesta = client.post(
            "/api/inventario/movimientos",
            json={
                "tipo": "entrada",
                "producto_id": ids[1],
                "cantidad": 1,
                "costo_unitario": 100,
                "motivo": f"Entrada {numero}",
            },
        )

        assert respuesta.status_code == 201

    respuesta = client.get("/api/inventario/movimientos?limite=2")

    assert respuesta.status_code == 200
    assert len(respuesta.get_json()["movimientos"]) == 2
