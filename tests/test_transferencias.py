from decimal import Decimal

import pytest

from app.models import (
    Bodega,
    Inventario,
    Movimiento,
    Producto,
    ProductoSerial,
    Sucursal,
    Transferencia,
    Usuario,
    UsuarioSucursal,
    Empresa,
    db,
)
from app.services.contexto import ContextoOperacion
from app.services.inventario import ServicioInventario, StockInsuficiente
from app.services.transferencias import (
    ErrorTransferencia,
    EstadoTransferenciaInvalido,
    ServicioTransferencias,
)
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        plan = usuario.empresa.suscripcion_actual.plan
        plan.funciones = {**plan.funciones, "transferencias": True, "multibodega": True}
        origen = db.session.scalar(db.select(Bodega))
        sucursal_destino = Sucursal(empresa_id=usuario.empresa_id, codigo="DEST", nombre="Destino")
        db.session.add(sucursal_destino)
        db.session.flush()
        destino = Bodega(
            empresa_id=usuario.empresa_id,
            sucursal_id=sucursal_destino.id,
            codigo="DEST",
            nombre="Bodega destino",
        )
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="TR-1",
            nombre="Transferible",
            costo_referencia=100,
            precio_venta=200,
        )
        db.session.add_all([destino, producto])
        db.session.flush()
        db.session.add(
            UsuarioSucursal(
                empresa_id=usuario.empresa_id,
                usuario_id=usuario.id,
                sucursal_id=sucursal_destino.id,
            )
        )
        db.session.commit()
        contexto = ContextoOperacion(usuario.empresa_id, origen.sucursal, origen)
        ServicioInventario(usuario, contexto).entrada(
            producto_id=producto.id, cantidad=10, costo_unitario=100, motivo="Saldo inicial"
        )
        return usuario.id, origen.id, destino.id, producto.id


def _crear(ids, cantidad=4):
    return ServicioTransferencias(db.session.get(Usuario, ids[0])).crear(
        numero="T-001",
        bodega_origen_id=ids[1],
        bodega_destino_id=ids[2],
        items=[{"producto_id": ids[3], "cantidad": cantidad}],
    )


def test_solicitud_no_modifica_stock(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        transferencia = _crear(ids)
        ServicioTransferencias(db.session.get(Usuario, ids[0])).solicitar(transferencia.id)
        assert (
            db.session.scalar(db.select(Inventario.cantidad).where(Inventario.bodega_id == ids[1]))
            == 10
        )
        assert db.session.get(Transferencia, transferencia.id).estado == "solicitada"


def test_despacho_y_recepcion_generan_dos_movimientos(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioTransferencias(db.session.get(Usuario, ids[0]))
        transferencia = _crear(ids)
        servicio.solicitar(transferencia.id)
        servicio.despachar(transferencia.id)
        assert (
            db.session.scalar(db.select(Inventario.cantidad).where(Inventario.bodega_id == ids[1]))
            == 6
        )
        servicio.recibir(transferencia.id)
        assert (
            db.session.scalar(db.select(Inventario.cantidad).where(Inventario.bodega_id == ids[2]))
            == 4
        )
        movimientos = list(
            db.session.scalars(
                db.select(Movimiento)
                .where(
                    Movimiento.referencia_tipo == "transferencia",
                    Movimiento.referencia_id == transferencia.id,
                )
                .order_by(Movimiento.id)
            )
        )
        assert [m.cantidad for m in movimientos] == [Decimal("-4.000"), Decimal("4.000")]
        assert all(m.tipo == "transferencia" for m in movimientos)


def test_despacho_parcial_y_recepcion_con_diferencia(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioTransferencias(db.session.get(Usuario, ids[0]))
        transferencia = _crear(ids, 8)
        servicio.solicitar(transferencia.id)
        item_id = transferencia.items[0].id
        servicio.despachar(transferencia.id, {item_id: Decimal("6")})
        servicio.recibir(transferencia.id, {item_id: Decimal("5")})
        item = db.session.get(type(transferencia.items[0]), item_id)
        assert item.cantidad_solicitada == 8
        assert item.cantidad_despachada == 6
        assert item.cantidad_recibida == 5
        assert (
            db.session.scalar(db.select(Inventario.cantidad).where(Inventario.bodega_id == ids[2]))
            == 5
        )


def test_fallo_en_despacho_revierte_todos_los_items(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        segundo = Producto(
            empresa_id=usuario.empresa_id,
            codigo="TR-2",
            nombre="Sin stock",
            costo_referencia=1,
            precio_venta=2,
        )
        db.session.add(segundo)
        db.session.commit()
        servicio = ServicioTransferencias(usuario)
        transferencia = servicio.crear(
            numero="T-002",
            bodega_origen_id=ids[1],
            bodega_destino_id=ids[2],
            items=[
                {"producto_id": ids[3], "cantidad": 2},
                {"producto_id": segundo.id, "cantidad": 1},
            ],
        )
        servicio.solicitar(transferencia.id)
        with pytest.raises(StockInsuficiente):
            servicio.despachar(transferencia.id)
        assert db.session.get(Transferencia, transferencia.id).estado == "solicitada"
        assert (
            db.session.scalar(
                db.select(Inventario.cantidad).where(
                    Inventario.bodega_id == ids[1], Inventario.producto_id == ids[3]
                )
            )
            == 10
        )


def test_no_cancela_despues_del_despacho(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioTransferencias(db.session.get(Usuario, ids[0]))
        transferencia = _crear(ids)
        servicio.solicitar(transferencia.id)
        servicio.despachar(transferencia.id)
        with pytest.raises(EstadoTransferenciaInvalido):
            servicio.cancelar(transferencia.id, "Cancelar")


def test_no_recibe_mas_de_lo_despachado(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioTransferencias(db.session.get(Usuario, ids[0]))
        transferencia = _crear(ids)
        servicio.solicitar(transferencia.id)
        servicio.despachar(transferencia.id)
        with pytest.raises(ErrorTransferencia):
            servicio.recibir(transferencia.id, {transferencia.items[0].id: Decimal("5")})
        assert db.session.get(Transferencia, transferencia.id).estado == "en_transito"


def test_plan_sin_transferencias_rechaza_operacion(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        usuario.empresa.suscripcion_actual.plan.funciones = {}
        db.session.commit()
        with pytest.raises(PermissionError):
            _crear(ids)


def test_bodega_de_otra_empresa_es_rechazada(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        otra = Empresa(nombre="Empresa ajena", email="ajena-transferencia@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        sucursal = Sucursal(empresa_id=otra.id, codigo="AJENA", nombre="Ajena")
        db.session.add(sucursal)
        db.session.flush()
        bodega = Bodega(
            empresa_id=otra.id, sucursal_id=sucursal.id, codigo="AJENA", nombre="Bodega ajena"
        )
        db.session.add(bodega)
        db.session.commit()
        bodega_id = bodega.id
        with pytest.raises(PermissionError):
            ServicioTransferencias(db.session.get(Usuario, ids[0])).crear(
                numero="T-AJENA",
                bodega_origen_id=ids[1],
                bodega_destino_id=bodega_id,
                items=[{"producto_id": ids[3], "cantidad": 1}],
            )


def test_bodega_no_asignada_de_la_misma_empresa_es_rechazada(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        sucursal = Sucursal(empresa_id=usuario.empresa_id, codigo="NO-ASIG", nombre="No asignada")
        db.session.add(sucursal)
        db.session.flush()
        bodega = Bodega(
            empresa_id=usuario.empresa_id,
            sucursal_id=sucursal.id,
            codigo="NO-ASIG",
            nombre="No asignada",
        )
        db.session.add(bodega)
        db.session.commit()
        bodega_id = bodega.id
        with pytest.raises(PermissionError):
            ServicioTransferencias(usuario).crear(
                numero="T-NO-ASIG",
                bodega_origen_id=ids[1],
                bodega_destino_id=bodega_id,
                items=[{"producto_id": ids[3], "cantidad": 1}],
            )


def test_api_cubre_ciclo_completo_y_lista_diferencias(app, client):
    ids = _preparar(app, client)
    respuesta = client.post(
        "/api/transferencias",
        json={
            "numero": "API-001",
            "bodega_origen_id": ids[1],
            "bodega_destino_id": ids[2],
            "items": [{"producto_id": ids[3], "cantidad": "4"}],
        },
    )
    assert respuesta.status_code == 201
    transferencia_id = respuesta.get_json()["id"]
    assert client.post(f"/api/transferencias/{transferencia_id}/solicitar").status_code == 200
    assert client.post(f"/api/transferencias/{transferencia_id}/despachar").status_code == 200
    assert client.post(f"/api/transferencias/{transferencia_id}/recibir").status_code == 200
    listado = client.get("/api/transferencias?estado=recibida")
    assert listado.status_code == 200
    transferencia = listado.get_json()["transferencias"][0]
    assert transferencia["numero"] == "API-001"
    assert transferencia["items"][0]["diferencia"] == "0.000"


def test_api_no_expone_transferencia_de_sucursal_no_asignada(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        transferencia = _crear(ids)
        transferencia_id = transferencia.id
        # La asignación se resuelve por sucursal; se elimina la correspondiente al destino.
        destino = db.session.get(Bodega, ids[2])
        asignacion = db.session.scalar(
            db.select(UsuarioSucursal).where(
                UsuarioSucursal.usuario_id == usuario.id,
                UsuarioSucursal.sucursal_id == destino.sucursal_id,
            )
        )
        db.session.delete(asignacion)
        db.session.commit()
    assert client.get(f"/api/transferencias/{transferencia_id}").status_code == 403


def test_transferencia_serializada_mueve_serial_y_cambia_estados(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        producto = db.session.get(Producto, ids[3])
        producto.requiere_serial = True
        serial = ProductoSerial(
            empresa_id=producto.empresa_id,
            producto_id=producto.id,
            bodega_id=ids[1],
            numero_serial="TR-SER-001",
            estado="disponible",
        )
        db.session.add(serial)
        db.session.commit()
        servicio = ServicioTransferencias(db.session.get(Usuario, ids[0]))
        transferencia = servicio.crear(
            numero="T-SERIAL",
            bodega_origen_id=ids[1],
            bodega_destino_id=ids[2],
            items=[
                {
                    "producto_id": ids[3],
                    "cantidad": 1,
                    "seriales": ["TR-SER-001"],
                }
            ],
        )
        servicio.solicitar(transferencia.id)
        assert serial.estado == "reservado"
        servicio.despachar(transferencia.id)
        servicio.recibir(transferencia.id)
        assert serial.estado == "disponible"
        assert serial.bodega_id == ids[2]
        assert serial.transferencia_item_id is None
