from decimal import Decimal

import pytest

from app.models import (
    Bodega,
    Empresa,
    Inventario,
    Lote,
    Movimiento,
    MovimientoLote,
    OrdenCompra,
    PresentacionProducto,
    Producto,
    ProductoSerial,
    Proveedor,
    RecepcionCompra,
    RecepcionCompraItem,
    Usuario,
    db,
)
from app.services.compras import ErrorCompra, EstadoCompraInvalido, ServicioCompras
from tests.test_autenticacion import REGISTRO


def _preparar(app, client, *, trazabilidad=False):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        if trazabilidad:
            from app.models import (
                ConfiguracionEmpresa,
            )

            configuracion = db.session.scalar(db.select(ConfiguracionEmpresa))
            configuracion.opciones = {
                "rubro": "minimarket",
                "capacidades": {},
            }
            db.session.commit()

        usuario = db.session.scalar(db.select(Usuario))
        bodega = db.session.scalar(db.select(Bodega).where(Bodega.empresa_id == usuario.empresa_id))
        proveedor = Proveedor(empresa_id=usuario.empresa_id, nombre="Proveedor Uno", activo=True)
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="COMP-1",
            nombre="Comprable",
            costo_referencia=100,
            precio_venta=200,
            controla_lotes=trazabilidad,
            controla_vencimiento=trazabilidad,
            requiere_serial=trazabilidad,
        )
        db.session.add_all([proveedor, producto])
        db.session.commit()
        return usuario.id, bodega.id, proveedor.id, producto.id


def _crear(ids, *, numero="OC-001", cantidad=10, precio=100):
    return ServicioCompras(db.session.get(Usuario, ids[0])).crear(
        numero=numero,
        proveedor_id=ids[2],
        bodega_destino_id=ids[1],
        items=[
            {
                "producto_id": ids[3],
                "cantidad": cantidad,
                "precio_unitario": precio,
                "descuento": 100,
                "impuesto": 190,
            }
        ],
    )


def _enviar(servicio, orden):
    servicio.confirmar(orden.id)
    return servicio.enviar(orden.id)


def test_crear_borrador_calcula_totales_sin_modificar_stock(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        orden = _crear(ids)
        assert orden.estado == "borrador" and orden.subtotal == 1000 and orden.total == 1090
        assert db.session.scalar(db.select(db.func.count(Inventario.id))) == 0
        assert db.session.scalar(db.select(db.func.count(Movimiento.id))) == 0


def test_flujo_recepcion_parcial_y_total_actualiza_stock_y_costo(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioCompras(db.session.get(Usuario, ids[0]))
        orden = _crear(ids)
        _enviar(servicio, orden)
        item_id = orden.items[0].id
        primera = servicio.recibir(
            orden.id,
            numero="RC-001",
            items=[{"orden_item_id": item_id, "cantidad": 4, "costo_unitario": 100}],
        )
        assert primera.estado == "confirmada"
        assert db.session.get(OrdenCompra, orden.id).estado == "parcialmente_recibida"
        servicio.recibir(
            orden.id,
            numero="RC-002",
            items=[{"orden_item_id": item_id, "cantidad": 6, "costo_unitario": 200}],
        )
        inventario = db.session.scalar(db.select(Inventario))
        assert db.session.get(OrdenCompra, orden.id).estado == "recibida"
        assert inventario.cantidad == 10 and inventario.costo_promedio == Decimal("160.0000")
        assert (
            db.session.scalar(
                db.select(db.func.count(Movimiento.id)).where(
                    Movimiento.referencia_tipo == "recepcion_compra"
                )
            )
            == 2
        )


def test_no_permite_recibir_mas_de_lo_pendiente_y_revierte(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioCompras(db.session.get(Usuario, ids[0]))
        orden = _crear(ids)
        _enviar(servicio, orden)
        with pytest.raises(ErrorCompra):
            servicio.recibir(
                orden.id,
                numero="RC-MAYOR",
                items=[{"orden_item_id": orden.items[0].id, "cantidad": 11, "costo_unitario": 100}],
            )
        assert db.session.get(OrdenCompra, orden.id).estado == "enviada"
        assert db.session.scalar(db.select(db.func.count(RecepcionCompra.id))) == 0
        assert db.session.scalar(db.select(db.func.count(Inventario.id))) == 0


def test_recepcion_de_varios_items_es_atomica(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        segundo = Producto(
            empresa_id=usuario.empresa_id,
            codigo="COMP-2",
            nombre="Segundo",
            costo_referencia=10,
            precio_venta=20,
        )
        db.session.add(segundo)
        db.session.commit()
        servicio = ServicioCompras(usuario)
        orden = servicio.crear(
            numero="OC-ATOM",
            proveedor_id=ids[2],
            bodega_destino_id=ids[1],
            items=[
                {"producto_id": ids[3], "cantidad": 2, "precio_unitario": 100},
                {"producto_id": segundo.id, "cantidad": 1, "precio_unitario": 10},
            ],
        )
        _enviar(servicio, orden)
        with pytest.raises(ErrorCompra):
            servicio.recibir(
                orden.id,
                numero="RC-ATOM",
                items=[
                    {"orden_item_id": orden.items[0].id, "cantidad": 1},
                    {"orden_item_id": orden.items[1].id, "cantidad": 2},
                ],
            )
        assert db.session.scalar(db.select(db.func.count(Inventario.id))) == 0
        assert all(i.cantidad_recibida == 0 for i in db.session.get(OrdenCompra, orden.id).items)


def test_cancelacion_solo_antes_de_recibir(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioCompras(db.session.get(Usuario, ids[0]))
        orden = _crear(ids)
        _enviar(servicio, orden)
        servicio.recibir(
            orden.id,
            numero="RC-PARCIAL",
            items=[{"orden_item_id": orden.items[0].id, "cantidad": 1}],
        )
        with pytest.raises(EstadoCompraInvalido):
            servicio.cancelar(orden.id, "Ya no se necesita")


def test_recepcion_registra_lote_vencimiento_y_seriales(app, client):
    ids = _preparar(app, client, trazabilidad=True)
    with app.app_context():
        servicio = ServicioCompras(db.session.get(Usuario, ids[0]))
        orden = _crear(ids, cantidad=2)
        _enviar(servicio, orden)
        servicio.recibir(
            orden.id,
            numero="RC-TRAZA",
            items=[
                {
                    "orden_item_id": orden.items[0].id,
                    "cantidad": 2,
                    "numero_lote": "LOTE-1",
                    "fecha_vencimiento": "2028-12-31",
                    "seriales": ["SER-1", "SER-2"],
                }
            ],
        )
        lote = db.session.scalar(db.select(Lote))
        assert lote.cantidad == 2 and str(lote.fecha_vencimiento) == "2028-12-31"
        traza_lote = db.session.scalar(db.select(MovimientoLote))
        assert traza_lote is not None
        assert traza_lote.lote_id == lote.id
        assert traza_lote.cantidad == 2
        assert traza_lote.saldo_anterior == 0
        assert traza_lote.saldo_nuevo == 2
        assert set(db.session.scalars(db.select(ProductoSerial.numero_serial))) == {
            "SER-1",
            "SER-2",
        }


def test_trazabilidad_incompleta_revierte_toda_la_recepcion(app, client):
    ids = _preparar(app, client, trazabilidad=True)
    with app.app_context():
        servicio = ServicioCompras(db.session.get(Usuario, ids[0]))
        orden = _crear(ids, cantidad=2)
        _enviar(servicio, orden)
        with pytest.raises(ErrorCompra):
            servicio.recibir(
                orden.id,
                numero="RC-MALA",
                items=[
                    {
                        "orden_item_id": orden.items[0].id,
                        "cantidad": 2,
                        "numero_lote": "LOTE-1",
                        "fecha_vencimiento": "2028-12-31",
                        "seriales": ["SOLO-UNO"],
                    }
                ],
            )
        assert db.session.scalar(db.select(db.func.count(Lote.id))) == 0
        assert db.session.scalar(db.select(db.func.count(Inventario.id))) == 0


def test_rechaza_proveedor_de_otra_empresa(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        otra = Empresa(nombre="Empresa ajena", email="compras-ajena@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        proveedor = Proveedor(empresa_id=otra.id, nombre="Proveedor ajeno")
        db.session.add(proveedor)
        db.session.commit()
        with pytest.raises(PermissionError):
            ServicioCompras(db.session.get(Usuario, ids[0])).crear(
                numero="OC-AJENA",
                proveedor_id=proveedor.id,
                bodega_destino_id=ids[1],
                items=[{"producto_id": ids[3], "cantidad": 1, "precio_unitario": 10}],
            )


def test_api_compras_expone_flujo_en_espanol(app, client):
    ids = _preparar(app, client)
    respuesta = client.post(
        "/api/compras",
        json={
            "numero": "OC-API",
            "proveedor_id": ids[2],
            "bodega_destino_id": ids[1],
            "items": [{"producto_id": ids[3], "cantidad": 2, "precio_unitario": 100}],
        },
    )
    assert respuesta.status_code == 201 and respuesta.get_json()["estado"] == "borrador"
    orden_id = respuesta.get_json()["id"]
    assert client.post(f"/api/compras/{orden_id}/confirmar").get_json()["estado"] == "creada"


def test_api_compra_expone_datos_para_panel(
    app,
    client,
):
    ids = _preparar(app, client)

    respuesta = client.post(
        "/api/compras",
        json={
            "numero": "OC-PANEL-001",
            "proveedor_id": ids[2],
            "bodega_destino_id": ids[1],
            "fecha_entrega_esperada": "2026-09-15",
            "observaciones": "Compra para reposición",
            "items": [
                {
                    "producto_id": ids[3],
                    "cantidad": 5,
                    "precio_unitario": 120,
                    "descuento": 20,
                    "impuesto": 110,
                }
            ],
        },
    )

    assert respuesta.status_code == 201

    orden = respuesta.get_json()

    campos_orden = {
        "id",
        "numero",
        "estado",
        "proveedor_id",
        "proveedor_nombre",
        "bodega_destino_id",
        "fecha_orden",
        "fecha_entrega_esperada",
        "moneda",
        "subtotal",
        "descuento",
        "impuesto",
        "total",
        "observaciones",
        "motivo_cancelacion",
        "items",
    }

    assert campos_orden.issubset(orden)
    assert orden["proveedor_nombre"] == "Proveedor Uno"
    assert orden["fecha_entrega_esperada"] == "2026-09-15"
    assert orden["observaciones"] == "Compra para reposición"

    assert len(orden["items"]) == 1

    item = orden["items"][0]

    campos_item = {
        "id",
        "producto_id",
        "producto_codigo",
        "producto_nombre",
        "cantidad",
        "cantidad_recibida",
        "precio_unitario",
        "descuento",
        "impuesto",
        "total",
    }

    assert campos_item.issubset(item)
    assert item["producto_codigo"] == "COMP-1"
    assert item["producto_nombre"] == "Comprable"


def test_api_edita_borrador_y_recalcula_totales(
    app,
    client,
):
    ids = _preparar(app, client)

    creacion = client.post(
        "/api/compras",
        json={
            "numero": "OC-EDITAR-1",
            "proveedor_id": ids[2],
            "bodega_destino_id": ids[1],
            "items": [
                {
                    "producto_id": ids[3],
                    "cantidad": 2,
                    "precio_unitario": 100,
                }
            ],
        },
    )

    assert creacion.status_code == 201

    orden_id = creacion.get_json()["id"]

    edicion = client.patch(
        f"/api/compras/{orden_id}",
        json={
            "numero": "OC-EDITADA-1",
            "fecha_entrega_esperada": "2026-10-20",
            "observaciones": "Orden actualizada",
            "items": [
                {
                    "producto_id": ids[3],
                    "cantidad": 5,
                    "precio_unitario": 120,
                    "descuento": 20,
                    "impuesto": 110,
                }
            ],
        },
    )

    assert edicion.status_code == 200

    orden = edicion.get_json()

    assert orden["numero"] == "OC-EDITADA-1"
    assert orden["estado"] == "borrador"
    assert orden["fecha_entrega_esperada"] == "2026-10-20"
    assert orden["observaciones"] == "Orden actualizada"
    assert orden["subtotal"] == "600.00"
    assert orden["descuento"] == "20.00"
    assert orden["impuesto"] == "110.00"
    assert orden["total"] == "690.00"
    assert orden["items"][0]["cantidad"] == "5.000"


def _agregar_presentacion_compra(
    app,
    ids,
    *,
    codigo="CAJA-12",
    nombre="Caja de 12",
    abreviatura="cj",
    factor=12,
):
    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        presentacion = PresentacionProducto(
            empresa_id=usuario.empresa_id,
            producto_id=ids[3],
            codigo=codigo,
            nombre=nombre,
            abreviatura=abreviatura,
            factor_base=factor,
            activa=True,
        )
        db.session.add(presentacion)
        db.session.commit()

        return presentacion.id


def test_compra_por_presentacion_guarda_conversion(
    app,
    client,
):
    ids = _preparar(app, client)
    presentacion_id = _agregar_presentacion_compra(
        app,
        ids,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )

        orden = ServicioCompras(usuario).crear(
            numero="OC-CAJAS-001",
            proveedor_id=ids[2],
            bodega_destino_id=ids[1],
            items=[
                {
                    "producto_id": ids[3],
                    "presentacion_id": presentacion_id,
                    "cantidad": 2,
                    "precio_unitario": 12000,
                }
            ],
        )

        item = orden.items[0]

        assert item.cantidad == Decimal("24.000")
        assert item.cantidad_presentacion == Decimal("2.000")
        assert item.factor_conversion == Decimal("12.000")
        assert item.precio_presentacion == Decimal("12000.0000")
        assert item.precio_unitario == Decimal("1000.0000")
        assert item.total == Decimal("24000.00")
        assert orden.subtotal == Decimal("24000.00")


def test_compra_conserva_fotografia_presentacion(
    app,
    client,
):
    ids = _preparar(app, client)
    presentacion_id = _agregar_presentacion_compra(
        app,
        ids,
        codigo="DISPLAY-6",
        nombre="Display de 6",
        abreviatura="disp",
        factor=6,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )

        orden = ServicioCompras(usuario).crear(
            numero="OC-DISPLAY-001",
            proveedor_id=ids[2],
            bodega_destino_id=ids[1],
            items=[
                {
                    "producto_id": ids[3],
                    "presentacion_id": presentacion_id,
                    "cantidad": 3,
                    "precio_unitario": 6000,
                }
            ],
        )

        item = orden.items[0]

        assert item.presentacion_id == presentacion_id
        assert item.presentacion_codigo == "DISPLAY-6"
        assert item.presentacion_nombre == "Display de 6"
        assert item.presentacion_abreviatura == "disp"


def test_compra_sin_presentacion_mantiene_contrato(
    app,
    client,
):
    ids = _preparar(app, client)

    with app.app_context():
        orden = _crear(
            ids,
            numero="OC-BASE-001",
            cantidad=10,
            precio=100,
        )

        item = orden.items[0]

        assert item.cantidad == Decimal("10.000")
        assert item.cantidad_presentacion == Decimal("10.000")
        assert item.factor_conversion == Decimal("1.000")
        assert item.precio_presentacion == Decimal("100.0000")
        assert item.precio_unitario == Decimal("100.0000")
        assert item.presentacion_id is None
        assert orden.subtotal == Decimal("1000.00")


def test_compra_rechaza_presentacion_de_otro_producto(
    app,
    client,
):
    ids = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        producto_ajeno = Producto(
            empresa_id=usuario.empresa_id,
            codigo="OTRO-PRESENTACION",
            nombre="Otro producto",
            costo_referencia=0,
            precio_venta=0,
        )
        db.session.add(producto_ajeno)
        db.session.flush()

        presentacion = PresentacionProducto(
            empresa_id=usuario.empresa_id,
            producto_id=producto_ajeno.id,
            codigo="CAJA-6",
            nombre="Caja de 6",
            abreviatura="cj",
            factor_base=6,
            activa=True,
        )
        db.session.add(presentacion)
        db.session.commit()

        with pytest.raises(
            ErrorCompra,
            match="no pertenece",
        ):
            ServicioCompras(usuario).crear(
                numero="OC-PRESENTACION-AJENA",
                proveedor_id=ids[2],
                bodega_destino_id=ids[1],
                items=[
                    {
                        "producto_id": ids[3],
                        "presentacion_id": presentacion.id,
                        "cantidad": 2,
                        "precio_unitario": 6000,
                    }
                ],
            )


def test_recepcion_por_presentacion_convierte_a_base(
    app,
    client,
):
    ids = _preparar(app, client)
    presentacion_id = _agregar_presentacion_compra(
        app,
        ids,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        servicio = ServicioCompras(usuario)

        orden = servicio.crear(
            numero="OC-REC-CAJAS",
            proveedor_id=ids[2],
            bodega_destino_id=ids[1],
            items=[
                {
                    "producto_id": ids[3],
                    "presentacion_id": presentacion_id,
                    "cantidad": 2,
                    "precio_unitario": 12000,
                }
            ],
        )
        _enviar(servicio, orden)

        recepcion = servicio.recibir(
            orden.id,
            numero="RC-CAJA-001",
            items=[
                {
                    "orden_item_id": orden.items[0].id,
                    "cantidad_presentacion": 1,
                    "costo_presentacion": 12000,
                }
            ],
        )

        item_recepcion = recepcion.items[0]
        item_orden = orden.items[0]
        inventario = db.session.scalar(db.select(Inventario))

        assert item_recepcion.cantidad == Decimal("12.000")
        assert item_recepcion.cantidad_presentacion == Decimal("1.000")
        assert item_recepcion.factor_conversion == Decimal("12.000")
        assert item_recepcion.costo_presentacion == Decimal("12000.0000")
        assert item_recepcion.costo_unitario == Decimal("1000.0000")
        assert item_orden.cantidad_recibida == Decimal("12.000")
        assert orden.estado == "parcialmente_recibida"
        assert inventario.cantidad == Decimal("12.000")
        assert inventario.costo_promedio == Decimal("1000.0000")


def test_recepcion_presentacion_no_supera_pendiente(
    app,
    client,
):
    ids = _preparar(app, client)
    presentacion_id = _agregar_presentacion_compra(
        app,
        ids,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        servicio = ServicioCompras(usuario)

        orden = servicio.crear(
            numero="OC-REC-LIMITE",
            proveedor_id=ids[2],
            bodega_destino_id=ids[1],
            items=[
                {
                    "producto_id": ids[3],
                    "presentacion_id": presentacion_id,
                    "cantidad": 2,
                    "precio_unitario": 12000,
                }
            ],
        )
        _enviar(servicio, orden)

        with pytest.raises(
            ErrorCompra,
            match="supera",
        ):
            servicio.recibir(
                orden.id,
                numero="RC-CAJA-MAYOR",
                items=[
                    {
                        "orden_item_id": orden.items[0].id,
                        "cantidad_presentacion": 3,
                    }
                ],
            )

        assert db.session.scalar(db.select(db.func.count(RecepcionCompra.id))) == 0
        assert db.session.scalar(db.select(db.func.count(Inventario.id))) == 0


def test_recepcion_base_mantiene_compatibilidad(
    app,
    client,
):
    ids = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        servicio = ServicioCompras(usuario)
        orden = _crear(
            ids,
            numero="OC-REC-BASE",
            cantidad=10,
            precio=100,
        )
        _enviar(servicio, orden)

        recepcion = servicio.recibir(
            orden.id,
            numero="RC-BASE-001",
            items=[
                {
                    "orden_item_id": orden.items[0].id,
                    "cantidad": 4,
                    "costo_unitario": 100,
                }
            ],
        )

        item = recepcion.items[0]

        assert item.cantidad == Decimal("4.000")
        assert item.cantidad_presentacion == Decimal("4.000")
        assert item.factor_conversion == Decimal("1.000")
        assert item.costo_presentacion == Decimal("100.0000")
        assert item.costo_unitario == Decimal("100.0000")


def test_api_compra_expone_presentacion_comercial(
    app,
    client,
):
    ids = _preparar(app, client)
    presentacion_id = _agregar_presentacion_compra(
        app,
        ids,
        codigo="PACK-6",
        nombre="Pack de 6",
        abreviatura="pack",
        factor=6,
    )

    respuesta = client.post(
        "/api/compras",
        json={
            "numero": "OC-API-PACK",
            "proveedor_id": ids[2],
            "bodega_destino_id": ids[1],
            "items": [
                {
                    "producto_id": ids[3],
                    "presentacion_id": presentacion_id,
                    "cantidad": 3,
                    "precio_unitario": 6000,
                }
            ],
        },
    )

    assert respuesta.status_code == 201

    item = respuesta.get_json()["items"][0]

    assert item["presentacion_id"] == presentacion_id
    assert item["presentacion_codigo"] == "PACK-6"
    assert item["presentacion_nombre"] == "Pack de 6"
    assert item["presentacion_abreviatura"] == "pack"
    assert item["cantidad_presentacion"] == "3.000"
    assert item["factor_conversion"] == "6.000"
    assert item["precio_presentacion"] == "6000.0000"
    assert item["cantidad"] == "18.000"
    assert item["precio_unitario"] == "1000.0000"
    assert item["total"] == "18000.00"


def test_api_recepcion_expone_conversion_comercial(
    app,
    client,
):
    ids = _preparar(app, client)
    presentacion_id = _agregar_presentacion_compra(
        app,
        ids,
    )

    creacion = client.post(
        "/api/compras",
        json={
            "numero": "OC-API-RECEPCION",
            "proveedor_id": ids[2],
            "bodega_destino_id": ids[1],
            "items": [
                {
                    "producto_id": ids[3],
                    "presentacion_id": presentacion_id,
                    "cantidad": 2,
                    "precio_unitario": 12000,
                }
            ],
        },
    )

    assert creacion.status_code == 201

    orden = creacion.get_json()
    orden_id = orden["id"]
    item_id = orden["items"][0]["id"]

    assert client.post(f"/api/compras/{orden_id}/confirmar").status_code == 200
    assert client.post(f"/api/compras/{orden_id}/enviar").status_code == 200

    respuesta = client.post(
        f"/api/compras/{orden_id}/recepciones",
        json={
            "numero": "RC-API-CAJA",
            "items": [
                {
                    "orden_item_id": item_id,
                    "cantidad_presentacion": 1,
                    "costo_presentacion": 12000,
                }
            ],
        },
    )

    assert respuesta.status_code == 201

    datos = respuesta.get_json()

    assert datos["numero"] == "RC-API-CAJA"
    assert datos["estado"] == "confirmada"
    assert len(datos["items"]) == 1

    item = datos["items"][0]

    assert item["orden_item_id"] == item_id
    assert item["cantidad"] == "12.000"
    assert item["cantidad_presentacion"] == "1.000"
    assert item["factor_conversion"] == "12.000"
    assert item["costo_unitario"] == "1000.0000"
    assert item["costo_presentacion"] == "12000.0000"

    assert datos["orden"]["estado"] == "parcialmente_recibida"
    assert datos["orden"]["items"][0]["cantidad_recibida"] == "12.000"
