from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import (
    AlertaInventario,
    ConfiguracionEmpresa,
    Empresa,
    Inventario,
    Lote,
    Movimiento,
    MovimientoLote,
    Producto,
    Usuario,
    db,
)
from app.services.alertas import ServicioAlertas
from app.services.inventario import (
    ErrorInventario,
    StockInsuficiente,
)
from app.services.productos import ServicioProductos
from app.services.ventas import ServicioVentas
from tests.test_inventario import (
    _preparar,
    _servicio,
)


def _crear_lotes(
    app,
    client,
    lotes,
):
    ids = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        configuracion = db.session.scalar(
            db.select(ConfiguracionEmpresa).where(
                ConfiguracionEmpresa.empresa_id == usuario.empresa_id
            )
        )
        configuracion.opciones = {
            "rubro": "farmacia",
            "capacidades": {
                "inventario_farmaceutico": True,
            },
        }
        db.session.commit()

        producto = db.session.get(
            Producto,
            ids[1],
        )
        producto.controla_lotes = True
        producto.controla_vencimiento = True
        db.session.commit()

        for datos in lotes:
            _servicio(ids).entrada(
                producto_id=ids[1],
                cantidad=datos["cantidad"],
                costo_unitario=100,
                motivo="Carga inicial por lotes",
                numero_lote=datos["numero"],
                fecha_vencimiento=datos["fecha_vencimiento"],
            )

    return ids


def test_salida_aplica_fefo(
    app,
    client,
):
    hoy = date.today()

    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "LOTE-TARDIO",
                "fecha_vencimiento": hoy + timedelta(days=180),
                "cantidad": 5,
            },
            {
                "numero": "LOTE-PROXIMO",
                "fecha_vencimiento": hoy + timedelta(days=30),
                "cantidad": 5,
            },
        ],
    )

    with app.app_context():
        resultado = _servicio(ids).salida(
            producto_id=ids[1],
            cantidad=6,
            motivo="Venta FEFO",
        )

        lotes = {
            lote.numero: lote
            for lote in db.session.scalars(db.select(Lote).where(Lote.producto_id == ids[1]))
        }

        assert resultado.stock_nuevo == 4
        assert lotes["LOTE-PROXIMO"].cantidad == Decimal("0.000")
        assert lotes["LOTE-TARDIO"].cantidad == Decimal("4.000")


def test_salida_no_utiliza_lote_vencido(
    app,
    client,
):
    hoy = date.today()

    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "LOTE-VENCIDO",
                "fecha_vencimiento": hoy + timedelta(days=90),
                "cantidad": 5,
            },
        ],
    )

    with app.app_context():
        lote = db.session.scalar(db.select(Lote).where(Lote.numero == "LOTE-VENCIDO"))
        lote.fecha_vencimiento = hoy - timedelta(days=1)
        db.session.commit()

        with pytest.raises(StockInsuficiente):
            _servicio(ids).salida(
                producto_id=ids[1],
                cantidad=1,
                motivo="Salida no permitida",
            )

        inventario = db.session.scalar(
            db.select(Inventario).where(Inventario.producto_id == ids[1])
        )
        lote = db.session.scalar(db.select(Lote).where(Lote.producto_id == ids[1]))

        assert inventario.cantidad == 5
        assert lote.cantidad == 5


def test_salida_rechaza_lotes_validos_insuficientes(
    app,
    client,
):
    hoy = date.today()

    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "LOTE-VALIDO",
                "fecha_vencimiento": hoy + timedelta(days=60),
                "cantidad": 2,
            },
            {
                "numero": "LOTE-VENCIDO",
                "fecha_vencimiento": hoy + timedelta(days=120),
                "cantidad": 8,
            },
        ],
    )

    with app.app_context():
        lote_vencido = db.session.scalar(db.select(Lote).where(Lote.numero == "LOTE-VENCIDO"))
        lote_vencido.fecha_vencimiento = hoy - timedelta(days=2)
        db.session.commit()

        cantidad_movimientos = db.session.scalar(db.select(db.func.count(Movimiento.id)))

        with pytest.raises(StockInsuficiente):
            _servicio(ids).salida(
                producto_id=ids[1],
                cantidad=3,
                motivo="Stock FEFO insuficiente",
            )

        lote_valido = db.session.scalar(db.select(Lote).where(Lote.numero == "LOTE-VALIDO"))
        inventario = db.session.scalar(
            db.select(Inventario).where(Inventario.producto_id == ids[1])
        )

        assert lote_valido.cantidad == 2
        assert inventario.cantidad == 10
        assert db.session.scalar(db.select(db.func.count(Movimiento.id))) == cantidad_movimientos


def test_salida_registra_movimientos_por_lote(
    app,
    client,
):
    from app.models import MovimientoLote

    hoy = date.today()

    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "LOTE-A",
                "fecha_vencimiento": hoy + timedelta(days=20),
                "cantidad": 2,
            },
            {
                "numero": "LOTE-B",
                "fecha_vencimiento": hoy + timedelta(days=40),
                "cantidad": 4,
            },
        ],
    )

    with app.app_context():
        resultado = _servicio(ids).salida(
            producto_id=ids[1],
            cantidad=5,
            motivo="Venta trazable",
        )

        trazas = list(
            db.session.scalars(
                db.select(MovimientoLote)
                .where(MovimientoLote.movimiento_id == resultado.movimiento_id)
                .order_by(MovimientoLote.id)
            )
        )

        assert len(trazas) == 2
        assert [traza.cantidad for traza in trazas] == [
            Decimal("-2.000"),
            Decimal("-3.000"),
        ]

        for traza in trazas:
            assert traza.saldo_nuevo == traza.saldo_anterior + traza.cantidad


def test_movimiento_lote_es_inmutable(
    app,
    client,
):
    from app.models import MovimientoLote

    hoy = date.today()

    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "LOTE-INMUTABLE",
                "fecha_vencimiento": hoy + timedelta(days=90),
                "cantidad": 3,
            },
        ],
    )

    with app.app_context():
        _servicio(ids).salida(
            producto_id=ids[1],
            cantidad=1,
            motivo="Venta trazable",
        )

        traza = db.session.scalar(db.select(MovimientoLote))
        traza.cantidad = Decimal("-2.000")

        with pytest.raises(ValueError):
            db.session.commit()

        db.session.rollback()


def _preparar_controlado(
    app,
    client,
):
    ids = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        configuracion = db.session.scalar(
            db.select(ConfiguracionEmpresa).where(
                ConfiguracionEmpresa.empresa_id == usuario.empresa_id
            )
        )
        configuracion.opciones = {
            "rubro": "farmacia",
            "capacidades": {},
        }
        db.session.commit()

        ServicioProductos(usuario).editar(
            ids[1],
            controla_lotes=True,
            controla_vencimiento=True,
        )

        db.session.expire_all()

    with app.app_context():
        producto_verificado = db.session.get(
            Producto,
            ids[1],
        )

        assert producto_verificado.controla_lotes is True
        assert producto_verificado.controla_vencimiento is True

    # La fixture mantiene un contexto exterior;
    # fuerza que la siguiente petición consulte
    # nuevamente el producto desde la base.
    db.session.expire_all()

    return ids


def test_entrada_controlada_exige_lote(
    app,
    client,
):
    ids = _preparar_controlado(
        app,
        client,
    )

    with app.app_context():
        with pytest.raises(ErrorInventario):
            _servicio(ids).entrada(
                producto_id=ids[1],
                cantidad=2,
                costo_unitario=100,
                motivo="Entrada sin lote",
            )

        assert db.session.scalar(db.select(db.func.count(Inventario.id))) == 0
        assert db.session.scalar(db.select(db.func.count(Lote.id))) == 0


def test_entrada_crea_lote_y_trazabilidad(
    app,
    client,
):
    from app.models import MovimientoLote

    ids = _preparar_controlado(
        app,
        client,
    )
    vencimiento = date.today() + timedelta(days=180)

    with app.app_context():
        resultado = _servicio(ids).entrada(
            producto_id=ids[1],
            cantidad=4,
            costo_unitario=125,
            motivo="Compra manual",
            numero_lote="LOTE-ENTRADA",
            fecha_vencimiento=vencimiento,
        )

        lote = db.session.scalar(db.select(Lote).where(Lote.numero == "LOTE-ENTRADA"))
        traza = db.session.scalar(
            db.select(MovimientoLote).where(MovimientoLote.movimiento_id == resultado.movimiento_id)
        )
        inventario = db.session.scalar(
            db.select(Inventario).where(Inventario.producto_id == ids[1])
        )

        assert lote is not None
        assert lote.cantidad == Decimal("4.000")
        assert lote.fecha_vencimiento == vencimiento
        assert inventario.cantidad == 4
        assert traza.lote_id == lote.id
        assert traza.cantidad == Decimal("4.000")
        assert traza.saldo_anterior == 0
        assert traza.saldo_nuevo == 4


def test_entrada_rechaza_lote_vencido(
    app,
    client,
):
    ids = _preparar_controlado(
        app,
        client,
    )

    with app.app_context():
        with pytest.raises(ErrorInventario):
            _servicio(ids).entrada(
                producto_id=ids[1],
                cantidad=2,
                costo_unitario=100,
                motivo="Lote vencido",
                numero_lote="LOTE-VENCIDO",
                fecha_vencimiento=(date.today() - timedelta(days=1)),
            )

        assert db.session.scalar(db.select(db.func.count(Inventario.id))) == 0
        assert db.session.scalar(db.select(db.func.count(Lote.id))) == 0


def test_ajuste_global_controlado_es_rechazado(
    app,
    client,
):
    ids = _preparar_controlado(
        app,
        client,
    )
    vencimiento = date.today() + timedelta(days=90)

    with app.app_context():
        _servicio(ids).entrada(
            producto_id=ids[1],
            cantidad=5,
            costo_unitario=100,
            motivo="Entrada inicial",
            numero_lote="LOTE-AJUSTE",
            fecha_vencimiento=vencimiento,
        )

        with pytest.raises(ErrorInventario):
            _servicio(ids).ajuste(
                producto_id=ids[1],
                stock_final=3,
                motivo="Ajuste global",
            )

        lote = db.session.scalar(db.select(Lote).where(Lote.numero == "LOTE-AJUSTE"))
        inventario = db.session.scalar(
            db.select(Inventario).where(Inventario.producto_id == ids[1])
        )

        assert lote.cantidad == 5
        assert inventario.cantidad == 5


def test_devolucion_controlada_reintegra_lote(
    app,
    client,
):
    from app.models import MovimientoLote

    ids = _preparar_controlado(
        app,
        client,
    )
    vencimiento = date.today() + timedelta(days=120)

    with app.app_context():
        _servicio(ids).entrada(
            producto_id=ids[1],
            cantidad=3,
            costo_unitario=100,
            motivo="Entrada inicial",
            numero_lote="LOTE-DEVOLUCION",
            fecha_vencimiento=vencimiento,
        )

        _servicio(ids).salida(
            producto_id=ids[1],
            cantidad=1,
            motivo="Venta",
        )

        resultado = _servicio(ids).devolucion(
            producto_id=ids[1],
            cantidad=1,
            costo_unitario=100,
            motivo="Devolucion cliente",
            numero_lote="LOTE-DEVOLUCION",
            fecha_vencimiento=vencimiento,
        )

        lote = db.session.scalar(db.select(Lote).where(Lote.numero == "LOTE-DEVOLUCION"))
        traza = db.session.scalar(
            db.select(MovimientoLote).where(MovimientoLote.movimiento_id == resultado.movimiento_id)
        )

        assert lote.cantidad == 3
        assert traza.cantidad == 1
        assert traza.saldo_anterior == 2
        assert traza.saldo_nuevo == 3


def test_venta_confirmada_aplica_fefo_y_trazabilidad(
    app,
    client,
):
    hoy = date.today()

    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "VENTA-TARDIO",
                "fecha_vencimiento": hoy + timedelta(days=180),
                "cantidad": 5,
            },
            {
                "numero": "VENTA-PROXIMO",
                "fecha_vencimiento": hoy + timedelta(days=30),
                "cantidad": 5,
            },
        ],
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        servicio = ServicioVentas(usuario)

        venta = servicio.crear(
            numero="VTA-FEFO-001",
            bodega_id=ids[3],
            items=[
                {
                    "producto_id": ids[1],
                    "cantidad": 6,
                    "precio_unitario": 200,
                }
            ],
        )

        servicio.reservar(venta.id)
        servicio.confirmar(venta.id)

        lotes = {
            lote.numero: lote
            for lote in db.session.scalars(db.select(Lote).where(Lote.producto_id == ids[1]))
        }

        assert lotes["VENTA-PROXIMO"].cantidad == Decimal("0.000")
        assert lotes["VENTA-TARDIO"].cantidad == Decimal("4.000")

        movimiento = db.session.scalar(
            db.select(Movimiento).where(
                Movimiento.referencia_tipo == "venta",
                Movimiento.referencia_id == venta.id,
            )
        )

        assert movimiento is not None
        assert movimiento.cantidad == Decimal("-6.000")

        trazas = list(
            db.session.scalars(
                db.select(MovimientoLote)
                .where(MovimientoLote.movimiento_id == movimiento.id)
                .order_by(MovimientoLote.id)
            )
        )

        assert len(trazas) == 2

        trazas_por_lote = {
            db.session.get(
                Lote,
                traza.lote_id,
            ).numero: traza
            for traza in trazas
        }

        traza_proxima = trazas_por_lote["VENTA-PROXIMO"]
        traza_tardia = trazas_por_lote["VENTA-TARDIO"]

        assert traza_proxima.cantidad == Decimal("-5.000")
        assert traza_proxima.saldo_anterior == Decimal("5.000")
        assert traza_proxima.saldo_nuevo == Decimal("0.000")

        assert traza_tardia.cantidad == Decimal("-1.000")
        assert traza_tardia.saldo_anterior == Decimal("5.000")
        assert traza_tardia.saldo_nuevo == Decimal("4.000")


def test_venta_no_confirma_con_stock_vencido(
    app,
    client,
):
    hoy = date.today()

    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "VENTA-VENCIDO",
                "fecha_vencimiento": hoy + timedelta(days=30),
                "cantidad": 5,
            },
        ],
    )

    with app.app_context():
        lote = db.session.scalar(db.select(Lote).where(Lote.numero == "VENTA-VENCIDO"))
        lote.fecha_vencimiento = hoy - timedelta(days=1)
        db.session.commit()

        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        servicio = ServicioVentas(usuario)

        venta = servicio.crear(
            numero="VTA-VENCIDA-001",
            bodega_id=ids[3],
            items=[
                {
                    "producto_id": ids[1],
                    "cantidad": 2,
                    "precio_unitario": 200,
                }
            ],
        )

        servicio.reservar(venta.id)

        with pytest.raises(StockInsuficiente):
            servicio.confirmar(venta.id)

        db.session.expire_all()

        inventario = db.session.scalar(
            db.select(Inventario).where(
                Inventario.producto_id == ids[1],
                Inventario.bodega_id == ids[3],
            )
        )
        venta_actual = db.session.get(
            type(venta),
            venta.id,
        )
        lote_actual = db.session.get(
            Lote,
            lote.id,
        )

        assert venta_actual.estado == "reservada"
        assert inventario.cantidad == Decimal("5.000")
        assert inventario.cantidad_reservada == Decimal("2.000")
        assert lote_actual.cantidad == Decimal("5.000")

        movimiento_venta = db.session.scalar(
            db.select(Movimiento).where(
                Movimiento.referencia_tipo == "venta",
                Movimiento.referencia_id == venta.id,
            )
        )

        assert movimiento_venta is None


def test_api_entrada_controlada_recibe_lote(
    app,
    client,
):
    ids = _preparar_controlado(
        app,
        client,
    )
    vencimiento = date.today() + timedelta(days=180)

    respuesta_productos = client.get("/api/productos")

    assert respuesta_productos.status_code == 200

    productos_api = respuesta_productos.get_json()["productos"]
    producto_api = next(producto for producto in productos_api if producto["id"] == ids[1])

    assert producto_api["controla_lotes"] is True, producto_api
    assert producto_api["controla_vencimiento"] is True, producto_api

    respuesta = client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "entrada",
            "producto_id": ids[1],
            "cantidad": 4,
            "costo_unitario": 125,
            "motivo": "Entrada farmacéutica",
            "numero_lote": "API-LOTE-001",
            "fecha_vencimiento": vencimiento.isoformat(),
        },
    )

    assert respuesta.status_code == 201, respuesta.get_json()

    with app.app_context():
        lote = db.session.scalar(
            db.select(Lote).where(
                Lote.producto_id == ids[1],
                Lote.numero == "API-LOTE-001",
            )
        )

        assert lote is not None
        assert lote.cantidad == Decimal("4.000")
        assert lote.fecha_vencimiento == vencimiento

        movimiento = db.session.scalar(
            db.select(Movimiento).where(
                Movimiento.producto_id == ids[1],
                Movimiento.tipo == "entrada",
            )
        )

        traza = db.session.scalar(
            db.select(MovimientoLote).where(
                MovimientoLote.movimiento_id == movimiento.id,
                MovimientoLote.lote_id == lote.id,
            )
        )

        assert traza is not None
        assert traza.cantidad == Decimal("4.000")


def test_api_devolucion_controlada_recibe_lote(
    app,
    client,
):
    ids = _preparar_controlado(
        app,
        client,
    )
    vencimiento = date.today() + timedelta(days=120)

    with app.app_context():
        _servicio(ids).entrada(
            producto_id=ids[1],
            cantidad=5,
            costo_unitario=100,
            motivo="Entrada inicial",
            numero_lote="API-DEV-001",
            fecha_vencimiento=vencimiento,
        )

        _servicio(ids).salida(
            producto_id=ids[1],
            cantidad=2,
            motivo="Venta previa",
        )

    respuesta = client.post(
        "/api/inventario/movimientos",
        json={
            "tipo": "devolucion",
            "producto_id": ids[1],
            "cantidad": 1,
            "costo_unitario": 100,
            "motivo": "Devolución farmacéutica",
            "numero_lote": "API-DEV-001",
            "fecha_vencimiento": vencimiento.isoformat(),
        },
    )

    assert respuesta.status_code == 201

    with app.app_context():
        lote = db.session.scalar(
            db.select(Lote).where(
                Lote.producto_id == ids[1],
                Lote.numero == "API-DEV-001",
            )
        )

        assert lote.cantidad == Decimal("4.000")

        movimiento = db.session.scalar(
            db.select(Movimiento)
            .where(
                Movimiento.producto_id == ids[1],
                Movimiento.tipo == "devolucion",
            )
            .order_by(Movimiento.id.desc())
        )

        traza = db.session.scalar(
            db.select(MovimientoLote).where(
                MovimientoLote.movimiento_id == movimiento.id,
                MovimientoLote.lote_id == lote.id,
            )
        )

        assert traza is not None
        assert traza.cantidad == Decimal("1.000")


def test_api_lista_lotes_con_estado_vencimiento(
    app,
    client,
):
    hoy = date.today()

    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "API-VENCIDO",
                "fecha_vencimiento": hoy + timedelta(days=90),
                "cantidad": 2,
            },
            {
                "numero": "API-PROXIMO",
                "fecha_vencimiento": hoy + timedelta(days=10),
                "cantidad": 3,
            },
            {
                "numero": "API-VIGENTE",
                "fecha_vencimiento": hoy + timedelta(days=120),
                "cantidad": 4,
            },
        ],
    )

    with app.app_context():
        vencido = db.session.scalar(db.select(Lote).where(Lote.numero == "API-VENCIDO"))
        vencido.fecha_vencimiento = hoy - timedelta(days=2)
        db.session.commit()

    respuesta = client.get("/api/inventario/lotes")

    assert respuesta.status_code == 200

    datos = respuesta.get_json()

    assert datos["bodega_id"] == ids[3]
    assert "lotes" in datos

    lotes = {lote["numero"]: lote for lote in datos["lotes"]}

    assert set(lotes) == {
        "API-VENCIDO",
        "API-PROXIMO",
        "API-VIGENTE",
    }

    campos = {
        "id",
        "producto_id",
        "producto_codigo",
        "producto_nombre",
        "bodega_id",
        "numero",
        "fecha_fabricacion",
        "fecha_vencimiento",
        "dias_para_vencer",
        "estado_vencimiento",
        "cantidad",
        "costo_unitario",
        "valor",
        "activo",
    }

    assert campos.issubset(lotes["API-PROXIMO"])

    assert lotes["API-VENCIDO"]["estado_vencimiento"] == "vencido"
    assert lotes["API-VENCIDO"]["dias_para_vencer"] == -2

    assert lotes["API-PROXIMO"]["estado_vencimiento"] == "proximo_vencer"
    assert lotes["API-PROXIMO"]["dias_para_vencer"] == 10

    assert lotes["API-VIGENTE"]["estado_vencimiento"] == "vigente"
    assert lotes["API-VIGENTE"]["cantidad"] == "4.000"
    assert lotes["API-VIGENTE"]["valor"] == "400.00"


def test_api_filtra_lotes_por_estado_y_producto(
    app,
    client,
):
    hoy = date.today()

    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "FILTRO-PROXIMO",
                "fecha_vencimiento": hoy + timedelta(days=15),
                "cantidad": 2,
            },
            {
                "numero": "FILTRO-VIGENTE",
                "fecha_vencimiento": hoy + timedelta(days=100),
                "cantidad": 2,
            },
        ],
    )

    respuesta = client.get(
        "/api/inventario/lotes" f"?producto_id={ids[1]}" "&estado=proximo_vencer"
    )

    assert respuesta.status_code == 200

    lotes = respuesta.get_json()["lotes"]

    assert len(lotes) == 1
    assert lotes[0]["numero"] == "FILTRO-PROXIMO"
    assert lotes[0]["estado_vencimiento"] == "proximo_vencer"


def test_api_lotes_rechaza_empresa_sin_capacidad(
    app,
    client,
):
    _preparar(app, client)

    respuesta = client.get("/api/inventario/lotes")

    assert respuesta.status_code == 403

    error = respuesta.get_json()

    assert error["codigo"] == "capacidad_no_disponible"
    assert "farmac" in error["mensaje"].lower()


def test_servicio_general_rechaza_lote_directo(
    app,
    client,
):
    ids = _preparar(app, client)
    vencimiento = date.today() + timedelta(days=90)

    with app.app_context():
        with pytest.raises(ErrorInventario):
            _servicio(ids).entrada(
                producto_id=ids[1],
                cantidad=3,
                costo_unitario=100,
                motivo="Intento sin capacidad",
                numero_lote="BYPASS-001",
                fecha_vencimiento=vencimiento,
            )

        assert (
            db.session.scalar(db.select(db.func.count(Lote.id)).where(Lote.numero == "BYPASS-001"))
            == 0
        )

        assert (
            db.session.scalar(
                db.select(db.func.count(Movimiento.id)).where(Movimiento.producto_id == ids[1])
            )
            == 0
        )


def test_producto_sin_control_rechaza_lote_manual(
    app,
    client,
):
    ids = _preparar(app, client)

    with app.app_context():
        configuracion = db.session.scalar(db.select(ConfiguracionEmpresa))
        configuracion.opciones = {
            "rubro": "minimarket",
            "capacidades": {},
        }
        db.session.commit()

        with pytest.raises(ErrorInventario):
            _servicio(ids).entrada(
                producto_id=ids[1],
                cantidad=2,
                costo_unitario=100,
                motivo=("Producto no configurado " "para lotes"),
                numero_lote="SIN-CONTROL-001",
                fecha_vencimiento=(date.today() + timedelta(days=60)),
            )

        assert (
            db.session.scalar(
                db.select(db.func.count(Lote.id)).where(Lote.numero == "SIN-CONTROL-001")
            )
            == 0
        )


def test_alertas_identifican_cada_lote_por_vencimiento(
    app,
    client,
):
    hoy = date.today()

    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "ALERTA-VENCIDO",
                "fecha_vencimiento": hoy + timedelta(days=90),
                "cantidad": 2,
            },
            {
                "numero": "ALERTA-HOY",
                "fecha_vencimiento": hoy,
                "cantidad": 3,
            },
            {
                "numero": "ALERTA-PROXIMO",
                "fecha_vencimiento": hoy + timedelta(days=15),
                "cantidad": 4,
            },
            {
                "numero": "ALERTA-VIGENTE",
                "fecha_vencimiento": hoy + timedelta(days=120),
                "cantidad": 5,
            },
        ],
    )

    with app.app_context():
        lote_vencido = db.session.scalar(db.select(Lote).where(Lote.numero == "ALERTA-VENCIDO"))
        lote_vencido.fecha_vencimiento = hoy - timedelta(days=2)
        db.session.commit()

        usuario = db.session.get(
            Usuario,
            ids[0],
        )

        resultado = ServicioAlertas(usuario).generar()

        assert resultado.creadas >= 3

        alertas = list(
            db.session.scalars(
                db.select(AlertaInventario).where(
                    AlertaInventario.empresa_id == usuario.empresa_id,
                    AlertaInventario.lote_id.is_not(None),
                    AlertaInventario.estado == "activa",
                )
            )
        )

        alertas_por_lote = {
            db.session.get(
                Lote,
                alerta.lote_id,
            ).numero: alerta
            for alerta in alertas
        }

        assert set(alertas_por_lote) == {
            "ALERTA-VENCIDO",
            "ALERTA-HOY",
            "ALERTA-PROXIMO",
        }

        assert alertas_por_lote["ALERTA-VENCIDO"].tipo == "lote_vencido"
        assert alertas_por_lote["ALERTA-VENCIDO"].prioridad == "critica"

        assert alertas_por_lote["ALERTA-HOY"].tipo == "lote_vence_hoy"
        assert alertas_por_lote["ALERTA-HOY"].prioridad == "critica"

        assert alertas_por_lote["ALERTA-PROXIMO"].tipo == "lote_proximo_vencer"
        assert alertas_por_lote["ALERTA-PROXIMO"].prioridad == "alta"


def test_alertas_de_lote_no_se_duplican(
    app,
    client,
):
    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "ALERTA-UNICA",
                "fecha_vencimiento": date.today() + timedelta(days=10),
                "cantidad": 3,
            },
        ],
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        servicio = ServicioAlertas(usuario)

        servicio.generar()
        servicio.generar()

        lote = db.session.scalar(db.select(Lote).where(Lote.numero == "ALERTA-UNICA"))

        cantidad = db.session.scalar(
            db.select(db.func.count(AlertaInventario.id)).where(
                AlertaInventario.lote_id == lote.id,
                AlertaInventario.tipo == "lote_proximo_vencer",
                AlertaInventario.estado == "activa",
            )
        )

        assert cantidad == 1


def test_alerta_de_lote_se_resuelve_al_agotarse(
    app,
    client,
):
    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "ALERTA-AGOTADA",
                "fecha_vencimiento": date.today() + timedelta(days=10),
                "cantidad": 2,
            },
        ],
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            ids[0],
        )
        servicio = ServicioAlertas(usuario)

        servicio.generar()

        lote = db.session.scalar(db.select(Lote).where(Lote.numero == "ALERTA-AGOTADA"))

        alerta = db.session.scalar(
            db.select(AlertaInventario).where(
                AlertaInventario.lote_id == lote.id,
                AlertaInventario.estado == "activa",
            )
        )

        assert alerta is not None

        lote.cantidad = Decimal("0.000")
        db.session.commit()

        servicio.generar()
        db.session.refresh(alerta)

        assert alerta.estado == "resuelta"
        assert alerta.resuelta_en is not None


def test_api_alertas_expone_informacion_del_lote(
    app,
    client,
):
    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "API-ALERTA-LOTE",
                "fecha_vencimiento": date.today() + timedelta(days=12),
                "cantidad": 6,
            },
        ],
    )

    generacion = client.post("/api/alertas/generar")

    assert generacion.status_code == 200

    respuesta = client.get(
        "/api/alertas" "?estado=activa" "&tipo=lote_proximo_vencer" f"&bodega_id={ids[3]}"
    )

    assert respuesta.status_code == 200

    datos = respuesta.get_json()
    alertas = datos["alertas"]

    assert len(alertas) == 1

    alerta = alertas[0]

    with app.app_context():
        lote = db.session.scalar(db.select(Lote).where(Lote.numero == "API-ALERTA-LOTE"))

        assert alerta["lote_id"] == lote.id

    assert alerta["tipo"] == "lote_proximo_vencer"
    assert alerta["producto_id"] == ids[1]
    assert alerta["bodega_id"] == ids[3]
    assert alerta["datos"]["numero_lote"] == "API-ALERTA-LOTE"
    assert alerta["datos"]["dias_para_vencer"] == 12
    assert alerta["datos"]["cantidad"] == "6.000"
    assert alerta["datos"]["fecha_vencimiento"] == (date.today() + timedelta(days=12)).isoformat()


def test_comando_automatico_genera_alertas_sin_sesion(
    app,
    client,
):
    ids = _crear_lotes(
        app,
        client,
        [
            {
                "numero": "CRON-LOTE-001",
                "fecha_vencimiento": date.today() + timedelta(days=14),
                "cantidad": 7,
            },
        ],
    )

    runner = app.test_cli_runner()

    primera = runner.invoke(args=["generar-alertas"])

    assert primera.exit_code == 0, primera.output or repr(primera.exception)
    assert "Empresas procesadas: 1" in primera.output
    assert "Errores: 0" in primera.output

    segunda = runner.invoke(args=["generar-alertas"])

    assert segunda.exit_code == 0, segunda.output or repr(segunda.exception)

    with app.app_context():
        lote = db.session.scalar(db.select(Lote).where(Lote.numero == "CRON-LOTE-001"))

        alertas = list(
            db.session.scalars(
                db.select(AlertaInventario).where(
                    AlertaInventario.empresa_id == lote.empresa_id,
                    AlertaInventario.lote_id == lote.id,
                    AlertaInventario.tipo == "lote_proximo_vencer",
                    AlertaInventario.estado == "activa",
                )
            )
        )

        assert len(alertas) == 1
        assert alertas[0].bodega_id == ids[3]


def test_comando_automatico_aisla_varias_empresas(
    app,
    client,
):
    _crear_lotes(
        app,
        client,
        [
            {
                "numero": "MULTIEMPRESA-001",
                "fecha_vencimiento": date.today() + timedelta(days=18),
                "cantidad": 4,
            },
        ],
    )

    with app.app_context():
        db.session.add(
            Empresa(
                nombre="Empresa sin operador",
                email=("empresa-sin-operador" "@example.com"),
                estado="activa",
            )
        )
        db.session.commit()

    resultado = app.test_cli_runner().invoke(args=["generar-alertas"])

    assert resultado.exit_code == 0, resultado.output or repr(resultado.exception)
    assert "Empresas procesadas: 1" in resultado.output
    assert "Empresas omitidas: 1" in resultado.output
    assert "Errores: 0" in resultado.output

    with app.app_context():
        alerta = db.session.scalar(
            db.select(AlertaInventario)
            .join(
                Lote,
                Lote.id == AlertaInventario.lote_id,
            )
            .where(
                Lote.numero == "MULTIEMPRESA-001",
                AlertaInventario.estado == "activa",
            )
        )

        assert alerta is not None
        assert alerta.tipo == "lote_proximo_vencer"
