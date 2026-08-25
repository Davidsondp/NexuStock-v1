from app.models import (
    AccesoEmpresaUsuario,
    Bodega,
    Caja,
    DocumentoTributario,
    Empresa,
    EventoIntegracion,
    GrupoEmpresa,
    IntegracionEmpresa,
    MembresiaGrupoEmpresa,
    OrdenWMS,
    PagoVenta,
    Producto,
    TurnoCaja,
    Usuario,
    Venta,
    db,
)
from app.services.contexto import ContextoOperacion
from app.services.inventario import ServicioInventario
from app.services.suite_comercial import (
    ServicioDTE,
    ServicioGrupoEmpresarial,
    ServicioIntegraciones,
    ServicioPOS,
    ServicioWMS,
)
import json
import time
import pytest
from app.services.ventas import ServicioVentas
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        usuario.empresa.direccion = "Av. Principal 123"
        usuario.empresa.ciudad = "Santiago"
        usuario.empresa.suscripcion_actual.plan.funciones.update(
            {"multiempresa": True, "pos": True, "wms": True, "dte": True, "integraciones": True}
        )
        bodega = db.session.scalar(db.select(Bodega).where(Bodega.empresa_id == usuario.empresa_id))
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="COM-1",
            nombre="Comercial",
            costo_referencia=100,
            precio_venta=200,
        )
        caja = Caja(
            empresa_id=usuario.empresa_id,
            sucursal_id=bodega.sucursal_id,
            codigo="CAJA-1",
            nombre="Caja principal",
        )
        db.session.add_all([producto, caja])
        db.session.commit()
        ServicioInventario(
            usuario, ContextoOperacion(usuario.empresa_id, bodega.sucursal, bodega)
        ).entrada(producto_id=producto.id, cantidad=20, costo_unitario=100, motivo="Inicial")
        return usuario.id, bodega.id, producto.id, caja.id


def test_pos_turno_venta_idempotente_y_cierre(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioPOS(db.session.get(Usuario, ids[0]))
        turno = servicio.abrir(ids[3], 1000)
        venta, creada = servicio.vender(
            turno.id,
            numero="POS-1",
            bodega_id=ids[1],
            items=[{"producto_id": ids[2], "cantidad": 2, "precio_unitario": 200}],
            pagos=[{"metodo": "efectivo", "monto": 400}],
            clave_idempotencia="venta-pos-1",
        )
        repetida, creada_otra_vez = servicio.vender(
            turno.id,
            numero="IGNORADA",
            bodega_id=ids[1],
            items=[],
            pagos=[],
            clave_idempotencia="venta-pos-1",
        )
        assert creada and not creada_otra_vez and repetida.id == venta.id
        assert db.session.scalar(db.select(db.func.count(PagoVenta.id))) == 1
        cerrado = servicio.cerrar(turno.id, 1400)
        assert cerrado.estado == "cerrado" and cerrado.diferencia == 0


def test_wms_guia_picking_packing_y_despacho(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        ventas = ServicioVentas(usuario)
        venta = ventas.crear(
            numero="WMS-1",
            bodega_id=ids[1],
            items=[{"producto_id": ids[2], "cantidad": 3, "precio_unitario": 200}],
        )
        ventas.reservar(venta.id)
        wms = ServicioWMS(usuario)
        orden = wms.crear(venta.id, "OW-1")
        orden = wms.avanzar(orden.id)
        wms.escanear(orden.id, etapa="picking", codigo_producto="COM-1", cantidad=3)
        orden = wms.avanzar(orden.id)
        orden = wms.avanzar(orden.id)
        wms.escanear(orden.id, etapa="packing", codigo_producto="COM-1", cantidad=3)
        orden = wms.avanzar(orden.id)
        orden = wms.avanzar(orden.id, transportista="Blue Express", seguimiento="TRACK-1")
        assert orden.estado == "despachada"
        assert db.session.get(Venta, venta.id).estado == "confirmada"


def test_dte_proveedor_certificado_e_idempotencia(app, client):
    ids = _preparar(app, client)

    class ClienteDTE:
        llamadas = 0

        def emitir(self, datos, clave):
            self.llamadas += 1
            self.datos = datos
            return {"folio": 101, "referencia": "DTE-101", "estado": "aceptado"}

    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        ventas = ServicioVentas(usuario)
        venta = ventas.crear(
            numero="DTE-1",
            bodega_id=ids[1],
            items=[{"producto_id": ids[2], "cantidad": 1, "precio_unitario": 200}],
        )
        ventas.reservar(venta.id)
        ventas.confirmar(venta.id)
        cliente = ClienteDTE()
        servicio = ServicioDTE(usuario)
        primero, creado = servicio.emitir(
            venta.id,
            tipo="boleta",
            proveedor="certificado",
            clave_idempotencia="dte-1",
            cliente=cliente,
        )
        segundo, repetido = servicio.emitir(
            venta.id,
            tipo="boleta",
            proveedor="certificado",
            clave_idempotencia="dte-1",
            cliente=cliente,
        )
        assert creado and not repetido and primero.id == segundo.id and cliente.llamadas == 1
        assert cliente.datos["emisor"]["rut"] == "76.123.456-0"
        assert cliente.datos["items"][0]["codigo"] == "COM-1"
        assert cliente.datos["totales"]["total"] == "200.00"
        assert db.session.scalar(db.select(db.func.count(DocumentoTributario.id))) == 1


def test_integracion_webhook_es_idempotente(app, client):
    ids = _preparar(app, client)
    secreto = "secreto-integracion-seguro-123"
    with app.app_context():
        integracion = ServicioIntegraciones(db.session.get(Usuario, ids[0])).crear(
            "shopify", secreto
        )
        cuerpo = json.dumps({"id": 1}, separators=(",", ":")).encode()
        marca = int(time.time())
        firma = ServicioIntegraciones.firmar_webhook(secreto, marca, cuerpo)
        uno, procesado = ServicioIntegraciones.recibir(
            integracion.id, "evt-1", "pedido", {"id": 1}, firma, marca, cuerpo
        )
        dos, reprocesado = ServicioIntegraciones.recibir(
            integracion.id, "evt-1", "pedido", {"id": 1}, firma, marca, cuerpo
        )
        assert procesado and not reprocesado and uno.id == dos.id
        assert db.session.scalar(db.select(db.func.count(EventoIntegracion.id))) == 1


def test_integracion_rechaza_firma_expirada_y_elimina_secretos(app, client):
    ids = _preparar(app, client)
    secreto = "secreto-integracion-seguro-456"
    with app.app_context():
        integracion = ServicioIntegraciones(db.session.get(Usuario, ids[0])).crear(
            "shopify", secreto
        )
        payload = {"id": 2, "token": "no-conservar", "customer": {"email": "privado@test.cl"}}
        cuerpo = json.dumps(payload, separators=(",", ":")).encode()
        expirada = int(time.time()) - 301
        firma = ServicioIntegraciones.firmar_webhook(secreto, expirada, cuerpo)
        with pytest.raises(PermissionError):
            ServicioIntegraciones.recibir(
                integracion.id, "evt-exp", "pedido", payload, firma, expirada, cuerpo
            )
        marca = int(time.time())
        firma = ServicioIntegraciones.firmar_webhook(secreto, marca, cuerpo)
        evento, _ = ServicioIntegraciones.recibir(
            integracion.id, "evt-priv", "pedido", payload, firma, marca, cuerpo
        )
        assert "token" not in evento.payload
        assert "email" not in evento.payload["customer"]


def test_multiempresa_consolida_solo_empresas_autorizadas(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        segunda = Empresa(nombre="Filial", email="filial@nexustock.cl")
        tercera = Empresa(nombre="No autorizada", email="no-autorizada@nexustock.cl")
        grupo = GrupoEmpresa(nombre="Holding", codigo="HOLDING")
        db.session.add_all([segunda, tercera, grupo])
        db.session.flush()
        db.session.add_all(
            [
                MembresiaGrupoEmpresa(
                    grupo_id=grupo.id, empresa_id=usuario.empresa_id, rol="propietaria"
                ),
                MembresiaGrupoEmpresa(grupo_id=grupo.id, empresa_id=segunda.id, rol="filial"),
                MembresiaGrupoEmpresa(grupo_id=grupo.id, empresa_id=tercera.id, rol="filial"),
                AccesoEmpresaUsuario(usuario_id=usuario.id, empresa_id=segunda.id, rol="consulta"),
            ]
        )
        db.session.commit()
        resumen = ServicioGrupoEmpresarial(usuario).resumen()
        assert {e["id"] for e in resumen["empresas"]} == {usuario.empresa_id, segunda.id}


def test_plan_sin_pos_ni_dte_rechaza_operaciones(
    app,
    client,
):
    ids = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        plan = usuario.empresa.suscripcion_actual.plan
        plan.funciones = {
            **(plan.funciones or {}),
            "pos": False,
            "dte": False,
        }
        db.session.commit()

        with pytest.raises(PermissionError):
            ServicioPOS(usuario).abrir(
                ids[3],
                1000,
            )

        with pytest.raises(PermissionError):
            ServicioDTE(usuario).emitir(
                999999,
                tipo="boleta",
                proveedor="certificado",
                clave_idempotencia="bloqueada",
                cliente=None,
            )

    respuesta_pos = client.post(
        "/api/comercial/pos/turnos",
        json={
            "caja_id": ids[3],
            "monto_apertura": 1000,
        },
    )

    assert respuesta_pos.status_code == 403
    assert respuesta_pos.get_json()["codigo"] == "plan_insuficiente"

    respuesta_dte = client.post(
        "/api/comercial/dte",
        json={},
    )

    assert respuesta_dte.status_code == 403
    assert respuesta_dte.get_json()["codigo"] == "plan_insuficiente"


def test_plan_sin_logistica_profesional_rechaza_wms_e_integraciones(
    app,
    client,
):
    ids = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        plan = usuario.empresa.suscripcion_actual.plan
        plan.funciones = {
            **(plan.funciones or {}),
            "wms": False,
            "integraciones": False,
        }
        db.session.commit()

        with pytest.raises(PermissionError):
            ServicioWMS(usuario).crear(
                venta_id=999999,
                numero="BLOQUEADA",
            )

        with pytest.raises(PermissionError):
            ServicioIntegraciones(usuario).crear(
                "shopify",
                "secreto-seguro-de-prueba-123",
            )

    respuesta_wms = client.post(
        "/api/comercial/wms/ordenes",
        json={},
    )
    assert respuesta_wms.status_code == 403
    assert respuesta_wms.get_json()["codigo"] == ("plan_insuficiente")

    respuesta_integracion = client.post(
        "/api/comercial/integraciones",
        json={},
    )
    assert respuesta_integracion.status_code == 403
    assert respuesta_integracion.get_json()["codigo"] == ("plan_insuficiente")
