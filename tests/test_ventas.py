from decimal import Decimal

import pytest

from app.models import (
    Bodega,
    Cliente,
    Empresa,
    Inventario,
    Movimiento,
    PresentacionProducto,
    Producto,
    ProductoSerial,
    Sucursal,
    Usuario,
    Venta,
    db,
)
from app.services.contexto import ContextoOperacion
from app.services.inventario import ServicioInventario, StockInsuficiente
from app.services.ventas import (
    ErrorVenta,
    EstadoVentaInvalido,
    ServicioVentas,
)
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        u = db.session.scalar(db.select(Usuario))
        b = db.session.scalar(db.select(Bodega).where(Bodega.empresa_id == u.empresa_id))
        p = Producto(
            empresa_id=u.empresa_id,
            codigo="V-1",
            nombre="Vendible",
            costo_referencia=100,
            precio_venta=200,
        )
        db.session.add(p)
        db.session.commit()
        ServicioInventario(u, ContextoOperacion(u.empresa_id, b.sucursal, b)).entrada(
            producto_id=p.id, cantidad=10, costo_unitario=100, motivo="Inicial"
        )
        return u.id, b.id, p.id


def _crear(ids, cantidad=4, numero="VTA-1"):
    return ServicioVentas(db.session.get(Usuario, ids[0])).crear(
        numero=numero,
        bodega_id=ids[1],
        items=[{"producto_id": ids[2], "cantidad": cantidad, "precio_unitario": 200}],
    )


def test_borrador_no_modifica_existencias(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        v = _crear(ids)
        inv = db.session.scalar(db.select(Inventario))
        assert v.estado == "borrador" and inv.cantidad == 10 and inv.cantidad_reservada == 0


def test_reservar_y_confirmar_venta(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        s = ServicioVentas(db.session.get(Usuario, ids[0]))
        v = _crear(ids)
        s.reservar(v.id)
        inv = db.session.scalar(db.select(Inventario))
        assert inv.cantidad == 10 and inv.cantidad_reservada == 4
        s.confirmar(v.id)
        inv = db.session.scalar(db.select(Inventario))
        assert inv.cantidad == 6 and inv.cantidad_reservada == 0
        m = db.session.scalar(db.select(Movimiento).where(Movimiento.referencia_tipo == "venta"))
        assert m.cantidad == Decimal("-4.000") and m.precio_unitario == 200


def test_reserva_sin_stock_revierte(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        v = _crear(ids, 11)
        with pytest.raises(StockInsuficiente):
            ServicioVentas(db.session.get(Usuario, ids[0])).reservar(v.id)
        assert (
            db.session.get(Venta, v.id).estado == "borrador"
            and db.session.scalar(db.select(Inventario.cantidad_reservada)) == 0
        )


def test_cancelar_libera_reserva(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        s = ServicioVentas(db.session.get(Usuario, ids[0]))
        v = _crear(ids)
        s.reservar(v.id)
        s.cancelar(v.id, "Cliente desistió")
        assert (
            db.session.scalar(db.select(Inventario.cantidad_reservada)) == 0
            and db.session.get(Venta, v.id).estado == "cancelada"
        )


def test_confirmada_no_se_cancela(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        s = ServicioVentas(db.session.get(Usuario, ids[0]))
        v = _crear(ids)
        s.reservar(v.id)
        s.confirmar(v.id)
        with pytest.raises(EstadoVentaInvalido):
            s.cancelar(v.id, "Inválida")


def test_producto_ajeno_es_rechazado(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        e = Empresa(nombre="Ajena", email="venta-ajena@nexustock.cl")
        db.session.add(e)
        db.session.flush()
        p = Producto(
            empresa_id=e.id, codigo="AJ", nombre="Ajeno", costo_referencia=1, precio_venta=2
        )
        db.session.add(p)
        db.session.commit()
        with pytest.raises(PermissionError):
            ServicioVentas(db.session.get(Usuario, ids[0])).crear(
                numero="AJ", bodega_id=ids[1], items=[{"producto_id": p.id, "cantidad": 1}]
            )


def test_api_venta_en_espanol(app, client):
    ids = _preparar(app, client)
    respuesta = client.post(
        "/api/ventas",
        json={
            "numero": "V-API",
            "bodega_id": ids[1],
            "items": [{"producto_id": ids[2], "cantidad": 2}],
        },
    )
    assert respuesta.status_code == 201
    assert respuesta.get_json()["estado"] == "borrador"
    venta_id = respuesta.get_json()["id"]
    assert client.post(f"/api/ventas/{venta_id}/reservar").get_json()["estado"] == "reservada"


def test_venta_serializada_reserva_confirma_y_expone_seriales(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        producto = db.session.get(Producto, ids[2])
        producto.requiere_serial = True
        db.session.add_all(
            [
                ProductoSerial(
                    empresa_id=producto.empresa_id,
                    producto_id=producto.id,
                    bodega_id=ids[1],
                    numero_serial=numero,
                    estado="disponible",
                )
                for numero in ("SER-001", "SER-002")
            ]
        )
        db.session.commit()
    respuesta = client.post(
        "/api/ventas",
        json={
            "numero": "V-SERIAL",
            "bodega_id": ids[1],
            "items": [
                {
                    "producto_id": ids[2],
                    "cantidad": 2,
                    "precio_unitario": 200,
                    "seriales": ["SER-001", "SER-002"],
                }
            ],
        },
    )
    assert respuesta.status_code == 201
    venta_id = respuesta.get_json()["id"]
    assert respuesta.get_json()["items"][0]["seriales"] == ["SER-001", "SER-002"]
    assert client.post(f"/api/ventas/{venta_id}/reservar").status_code == 200
    with app.app_context():
        assert set(db.session.scalars(db.select(ProductoSerial.estado))) == {"reservado"}
    assert client.post(f"/api/ventas/{venta_id}/confirmar").status_code == 200
    with app.app_context():
        seriales = list(db.session.scalars(db.select(ProductoSerial)))
        assert {serial.estado for serial in seriales} == {"salido"}
        assert all(serial.fecha_salida for serial in seriales)


def test_venta_serializada_exige_serial_por_unidad(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        db.session.get(Producto, ids[2]).requiere_serial = True
        db.session.commit()
    respuesta = client.post(
        "/api/ventas",
        json={
            "numero": "V-SIN-SERIAL",
            "bodega_id": ids[1],
            "items": [{"producto_id": ids[2], "cantidad": 1}],
        },
    )
    assert respuesta.status_code == 400
    assert "serial disponible" in respuesta.get_json()["mensaje"]


def test_api_venta_expone_datos_para_panel(
    app,
    client,
):
    ids = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])

        cliente = Cliente(
            empresa_id=usuario.empresa_id,
            nombre="Cliente de prueba",
            identificacion_fiscal="12.345.678-5",
            email="cliente@nexustock.cl",
            activo=True,
        )

        db.session.add(cliente)
        db.session.commit()

        cliente_id = cliente.id

    respuesta = client.post(
        "/api/ventas",
        json={
            "numero": "VTA-PANEL-001",
            "bodega_id": ids[1],
            "cliente_id": cliente_id,
            "moneda": "CLP",
            "observaciones": "Venta para panel",
            "items": [
                {
                    "producto_id": ids[2],
                    "cantidad": 2,
                    "precio_unitario": 250,
                    "descuento": 20,
                    "impuesto": 90,
                }
            ],
        },
    )

    assert respuesta.status_code == 201

    venta = respuesta.get_json()

    campos_venta = {
        "id",
        "numero",
        "estado",
        "cliente_id",
        "cliente_nombre",
        "bodega_id",
        "fecha_creacion",
        "confirmada_en",
        "cancelada_en",
        "motivo_cancelacion",
        "moneda",
        "subtotal",
        "descuento",
        "impuesto",
        "total",
        "observaciones",
        "items",
    }

    assert campos_venta.issubset(venta)
    assert venta["cliente_nombre"] == "Cliente de prueba"
    assert venta["observaciones"] == "Venta para panel"

    assert len(venta["items"]) == 1

    item = venta["items"][0]

    campos_item = {
        "id",
        "producto_id",
        "producto_codigo",
        "producto_nombre",
        "cantidad",
        "precio_unitario",
        "descuento",
        "impuesto",
        "total",
    }

    assert campos_item.issubset(item)
    assert item["producto_codigo"] == "V-1"
    assert item["producto_nombre"] == "Vendible"
    assert item["cantidad"] == "2.000"
    assert item["total"] == "570.00"


def _agregar_presentacion_venta(
    app,
    ids,
    *,
    codigo="PACK-4",
    nombre="Pack de 4",
    abreviatura="pack",
    factor=4,
):
    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        presentacion = PresentacionProducto(
            empresa_id=usuario.empresa_id,
            producto_id=ids[2],
            codigo=codigo,
            nombre=nombre,
            abreviatura=abreviatura,
            factor_base=factor,
            activa=True,
        )
        db.session.add(presentacion)
        db.session.commit()

        return presentacion.id


def test_venta_por_presentacion_guarda_conversion(
    app,
    client,
):
    ids = _preparar(app, client)
    presentacion_id = _agregar_presentacion_venta(
        app,
        ids,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )

        venta = ServicioVentas(usuario).crear(
            numero="VTA-PACK-001",
            bodega_id=ids[1],
            items=[
                {
                    "producto_id": ids[2],
                    "presentacion_id": presentacion_id,
                    "cantidad": 2,
                    "precio_unitario": 1000,
                }
            ],
        )

        item = venta.items[0]

        assert item.cantidad == Decimal("8.000")
        assert item.cantidad_presentacion == Decimal("2.000")
        assert item.factor_conversion == Decimal("4.000")
        assert item.precio_presentacion == Decimal("1000.00")
        assert item.precio_unitario == Decimal("250.00")
        assert item.total == Decimal("2000.00")
        assert venta.subtotal == Decimal("2000.00")


def test_venta_conserva_fotografia_presentacion(
    app,
    client,
):
    ids = _preparar(app, client)
    presentacion_id = _agregar_presentacion_venta(
        app,
        ids,
        codigo="DISPLAY-5",
        nombre="Display de 5",
        abreviatura="disp",
        factor=5,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )

        venta = ServicioVentas(usuario).crear(
            numero="VTA-DISPLAY-001",
            bodega_id=ids[1],
            items=[
                {
                    "producto_id": ids[2],
                    "presentacion_id": presentacion_id,
                    "cantidad": 1,
                    "precio_unitario": 1250,
                }
            ],
        )

        item = venta.items[0]

        assert item.presentacion_id == presentacion_id
        assert item.presentacion_codigo == "DISPLAY-5"
        assert item.presentacion_nombre == "Display de 5"
        assert item.presentacion_abreviatura == "disp"


def test_venta_presentacion_reserva_y_descuenta_base(
    app,
    client,
):
    ids = _preparar(app, client)
    presentacion_id = _agregar_presentacion_venta(
        app,
        ids,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        servicio = ServicioVentas(usuario)

        venta = servicio.crear(
            numero="VTA-PACK-STOCK",
            bodega_id=ids[1],
            items=[
                {
                    "producto_id": ids[2],
                    "presentacion_id": presentacion_id,
                    "cantidad": 2,
                    "precio_unitario": 1000,
                }
            ],
        )

        servicio.reservar(venta.id)

        inventario = db.session.scalar(db.select(Inventario))

        assert inventario.cantidad == Decimal("10.000")
        assert inventario.cantidad_reservada == Decimal("8.000")

        servicio.confirmar(venta.id)

        assert inventario.cantidad == Decimal("2.000")
        assert inventario.cantidad_reservada == Decimal("0.000")

        movimiento = db.session.scalar(
            db.select(Movimiento).where(Movimiento.referencia_tipo == "venta")
        )

        assert movimiento.cantidad == Decimal("-8.000")
        assert movimiento.precio_unitario == Decimal("250.00")


def test_venta_base_mantiene_compatibilidad(
    app,
    client,
):
    ids = _preparar(app, client)

    with app.app_context():
        venta = _crear(
            ids,
            cantidad=4,
            numero="VTA-BASE-001",
        )
        item = venta.items[0]

        assert item.cantidad == Decimal("4.000")
        assert item.cantidad_presentacion == Decimal("4.000")
        assert item.factor_conversion == Decimal("1.000")
        assert item.precio_presentacion == Decimal("200.00")
        assert item.precio_unitario == Decimal("200.00")
        assert item.presentacion_id is None


def test_venta_rechaza_presentacion_de_otro_producto(
    app,
    client,
):
    ids = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        otro = Producto(
            empresa_id=usuario.empresa_id,
            codigo="VENTA-OTRO",
            nombre="Otro producto",
            costo_referencia=10,
            precio_venta=20,
        )
        db.session.add(otro)
        db.session.flush()

        presentacion = PresentacionProducto(
            empresa_id=usuario.empresa_id,
            producto_id=otro.id,
            codigo="PACK-AJENO",
            nombre="Pack ajeno",
            abreviatura="pack",
            factor_base=4,
            activa=True,
        )
        db.session.add(presentacion)
        db.session.commit()

        with pytest.raises(
            ErrorVenta,
            match="no pertenece",
        ):
            ServicioVentas(usuario).crear(
                numero="VTA-PRESENTACION-AJENA",
                bodega_id=ids[1],
                items=[
                    {
                        "producto_id": ids[2],
                        "presentacion_id": presentacion.id,
                        "cantidad": 1,
                        "precio_unitario": 100,
                    }
                ],
            )


def test_api_venta_expone_presentacion_comercial(
    app,
    client,
):
    ids = _preparar(app, client)
    presentacion_id = _agregar_presentacion_venta(
        app,
        ids,
        codigo="PACK-4",
        nombre="Pack de 4",
        abreviatura="pack",
        factor=4,
    )

    respuesta = client.post(
        "/api/ventas",
        json={
            "numero": "VTA-API-PACK",
            "bodega_id": ids[1],
            "items": [
                {
                    "producto_id": ids[2],
                    "presentacion_id": presentacion_id,
                    "cantidad": 2,
                    "precio_unitario": 1000,
                }
            ],
        },
    )

    assert respuesta.status_code == 201

    venta = respuesta.get_json()
    item = venta["items"][0]

    assert item["presentacion_id"] == presentacion_id
    assert item["presentacion_codigo"] == "PACK-4"
    assert item["presentacion_nombre"] == "Pack de 4"
    assert item["presentacion_abreviatura"] == "pack"
    assert item["cantidad_presentacion"] == "2.000"
    assert item["factor_conversion"] == "4.000"
    assert item["precio_presentacion"] == "1000.00"

    # Valores normalizados en la unidad base.
    assert item["cantidad"] == "8.000"
    assert item["precio_unitario"] == "250.00"
    assert item["total"] == "2000.00"


def test_api_venta_base_expone_conversion_unitaria(
    app,
    client,
):
    ids = _preparar(app, client)

    respuesta = client.post(
        "/api/ventas",
        json={
            "numero": "VTA-API-BASE",
            "bodega_id": ids[1],
            "items": [
                {
                    "producto_id": ids[2],
                    "cantidad": 3,
                    "precio_unitario": 200,
                }
            ],
        },
    )

    assert respuesta.status_code == 201

    item = respuesta.get_json()["items"][0]

    assert item["presentacion_id"] is None
    assert item["presentacion_codigo"] is None
    assert item["presentacion_nombre"] is None
    assert item["presentacion_abreviatura"] is None
    assert item["cantidad_presentacion"] == "3.000"
    assert item["factor_conversion"] == "1.000"
    assert item["precio_presentacion"] == "200.00"
    assert item["cantidad"] == "3.000"
    assert item["precio_unitario"] == "200.00"
    assert item["total"] == "600.00"
