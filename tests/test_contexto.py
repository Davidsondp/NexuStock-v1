from pathlib import Path

from app.models import Auditoria, Bodega, Empresa, Sucursal, Usuario, UsuarioSucursal, db
from app.services.contexto import (
    CLAVE_BODEGA,
    CLAVE_SUCURSAL,
    establecer_contexto,
    obtener_contexto,
)
from tests.test_autenticacion import REGISTRO


def _registrar(client):
    client.post("/autenticacion/registro", data=REGISTRO)


def test_contexto_automatico_para_una_ubicacion(app, client):
    _registrar(client)
    with app.test_request_context():
        usuario = db.session.scalar(db.select(Usuario))
        contexto = obtener_contexto(usuario)
        assert contexto.empresa_id == usuario.empresa_id
        assert contexto.sucursal.codigo == "PRINCIPAL"
        assert contexto.bodega.codigo == "PRINCIPAL"


def test_no_permita_sucursal_de_otra_empresa(app, client):
    _registrar(client)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        otra = Empresa(nombre="Otra", email="otra@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        sucursal = Sucursal(empresa_id=otra.id, codigo="OTRA", nombre="Otra sucursal")
        db.session.add(sucursal)
        db.session.flush()
        bodega = Bodega(empresa_id=otra.id, sucursal_id=sucursal.id, codigo="OTRA", nombre="Otra")
        db.session.add(bodega)
        db.session.commit()
        ids = usuario.id, sucursal.id, bodega.id
    with app.test_request_context():
        usuario = db.session.get(Usuario, ids[0])
        try:
            establecer_contexto(usuario, ids[1], ids[2])
            assert False, "Debió rechazar el cruce entre empresas"
        except PermissionError:
            pass


def test_sesion_manipulada_se_limpia_y_revalida(app, client):
    _registrar(client)
    with client.session_transaction() as sesion:
        sesion[CLAVE_SUCURSAL] = 999999
        sesion[CLAVE_BODEGA] = 999999
    respuesta = client.get("/contexto/seleccionar")
    assert respuesta.status_code == 200
    with client.session_transaction() as sesion:
        assert CLAVE_SUCURSAL not in sesion
        assert CLAVE_BODEGA not in sesion


def test_api_bodegas_no_expone_otra_empresa(app, client):
    _registrar(client)
    with app.app_context():
        otra = Empresa(nombre="Otra", email="otra@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        sucursal = Sucursal(empresa_id=otra.id, codigo="OTRA", nombre="Otra")
        db.session.add(sucursal)
        db.session.flush()
        db.session.add(
            Bodega(empresa_id=otra.id, sucursal_id=sucursal.id, codigo="OTRA", nombre="Secreta")
        )
        db.session.commit()
        sucursal_id = sucursal.id
    respuesta = client.get(f"/contexto/bodegas/{sucursal_id}")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"bodegas": []}


def test_empleado_solo_ve_sucursales_asignadas(app, client):
    _registrar(client)
    with app.app_context():
        admin = db.session.scalar(db.select(Usuario))
        segunda = Sucursal(empresa_id=admin.empresa_id, codigo="DOS", nombre="Sucursal dos")
        db.session.add(segunda)
        db.session.flush()
        db.session.add(
            Bodega(
                empresa_id=admin.empresa_id,
                sucursal_id=segunda.id,
                codigo="DOS",
                nombre="Bodega dos",
            )
        )
        empleado = Usuario(
            empresa_id=admin.empresa_id,
            nombre="Empleado",
            email="empleado@nexustock.cl",
            rol="empleado",
        )
        empleado.set_password("ClaveEmpleado123")
        db.session.add(empleado)
        db.session.flush()
        principal = db.session.scalar(db.select(Sucursal).where(Sucursal.codigo == "PRINCIPAL"))
        db.session.add(
            UsuarioSucursal(
                empresa_id=admin.empresa_id,
                usuario_id=empleado.id,
                sucursal_id=principal.id,
                es_principal=True,
            )
        )
        db.session.commit()
    client.post("/autenticacion/salir")
    client.post(
        "/autenticacion/ingresar",
        data={"email": "empleado@nexustock.cl", "password": "ClaveEmpleado123"},
    )
    respuesta = client.get("/contexto/seleccionar")
    assert b"Sucursal principal" in respuesta.data
    assert b"Sucursal dos" not in respuesta.data


def test_seleccion_valida_guarda_contexto_y_audita(app, client):
    _registrar(client)
    with app.app_context():
        sucursal = db.session.scalar(db.select(Sucursal))
        bodega = db.session.scalar(db.select(Bodega))
        ids = sucursal.id, bodega.id
    respuesta = client.post(
        "/contexto/seleccionar", data={"sucursal_id": ids[0], "bodega_id": ids[1]}
    )
    assert respuesta.status_code == 302
    with client.session_transaction() as sesion:
        assert sesion[CLAVE_SUCURSAL] == ids[0]
        assert sesion[CLAVE_BODEGA] == ids[1]
    with app.app_context():
        auditoria = db.session.scalar(
            db.select(Auditoria).where(Auditoria.accion == "contexto.seleccionado")
        )
        assert auditoria is not None


def test_bodega_desactivada_invalida_contexto(app, client):
    _registrar(client)
    with app.app_context():
        sucursal = db.session.scalar(db.select(Sucursal))
        bodega = db.session.scalar(db.select(Bodega))
        ids = sucursal.id, bodega.id
    client.post("/contexto/seleccionar", data={"sucursal_id": ids[0], "bodega_id": ids[1]})
    with app.app_context():
        bodega = db.session.get(Bodega, ids[1])
        bodega.activa = False
        db.session.commit()
    client.get("/estado")
    with client.session_transaction() as sesion:
        assert CLAVE_SUCURSAL not in sesion
        assert CLAVE_BODEGA not in sesion


def test_selector_contexto_incluye_interfaz_visual(
    client,
):
    _registrar(client)

    respuesta = client.get("/contexto/seleccionar")

    assert respuesta.status_code == 200

    contratos = (
        b'data-api-bodegas-base="/contexto/bodegas"',
        b'id="selector-contexto"',
        b'id="sucursal_id"',
        b'id="bodega_id"',
        b'id="resumen-sucursal"',
        b'id="resumen-bodega"',
        b'id="estado-contexto"',
        b'id="volver-panel"',
        b"css/contexto.css",
        b"js/contexto.js",
    )

    for contrato in contratos:
        assert contrato in respuesta.data

    textos = (
        "Seleccionar ubicación",
        "Contexto operacional",
        "El inventario, las ventas y los reportes",
        "Sucursal autorizada",
        "Bodega de trabajo",
    )

    for texto in textos:
        assert texto.encode("utf-8") in respuesta.data


def test_javascript_contexto_actualiza_bodegas():
    contenido = Path("app/static/js/contexto.js").read_text(encoding="utf-8-sig")

    contratos = (
        "apiBodegasBase",
        "sucursal_id",
        "bodega_id",
        "resumen-sucursal",
        "resumen-bodega",
        "estado-contexto",
        "X-CSRFToken",
    )

    for contrato in contratos:
        assert contrato in contenido
