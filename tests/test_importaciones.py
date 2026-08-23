from io import BytesIO

from openpyxl import Workbook

from app.models import Inventario, Movimiento, Producto, Usuario, db
from tests.test_autenticacion import REGISTRO


def _habilitar(app):
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario).order_by(Usuario.id.desc()))
        plan = usuario.empresa.suscripcion_actual.plan
        plan.funciones = {**plan.funciones, "exportacion.avanzada": True}
        db.session.commit()
        return usuario.id


def _registrar(app, client, registro=None):
    client.post("/autenticacion/registro", data=registro or REGISTRO)
    usuario_id = _habilitar(app)
    client.get("/panel")
    return usuario_id


def _csv(client, contenido):
    return client.post(
        "/importaciones/previsualizar",
        data={"archivo": (BytesIO(contenido.encode()), "productos.csv")},
        content_type="multipart/form-data",
    )


def test_csv_previsualiza_y_confirma_productos_con_stock(app, client):
    _registrar(app, client)
    previa = _csv(
        client,
        "codigo,nombre,codigo_barras,costo,precio,stock_inicial\n"
        "IMP-1,Producto importado,780001,100,180,7\n",
    )
    assert previa.status_code == 200
    datos = previa.get_json()
    assert datos["total"] == 1 and datos["con_errores"] == 0

    confirmada = client.post("/importaciones/confirmar", json={"token": datos["token"]})
    assert confirmada.status_code == 200
    assert confirmada.get_json() == {
        "creados": 1,
        "actualizados": 0,
        "movimientos_stock": 1,
    }
    with app.app_context():
        producto = db.session.scalar(db.select(Producto).where(Producto.codigo == "IMP-1"))
        assert producto and producto.empresa_id
        assert db.session.scalar(db.select(Inventario.cantidad)) == 7
        assert db.session.scalar(db.select(Movimiento.referencia_tipo)) == "importacion"


def test_excel_es_admitido_y_solo_genera_vista_previa(app, client):
    _registrar(app, client)
    libro = Workbook()
    hoja = libro.active
    hoja.append(["codigo", "nombre", "precio"])
    hoja.append(["XLS-1", "Desde Excel", 2500])
    salida = BytesIO()
    libro.save(salida)
    respuesta = client.post(
        "/importaciones/previsualizar",
        data={"archivo": (BytesIO(salida.getvalue()), "catalogo.xlsx")},
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json()["filas"][0]["datos"]["codigo"] == "XLS-1"
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Producto.id))) == 0


def test_filas_invalidas_no_pueden_confirmarse(app, client):
    _registrar(app, client)
    previa = _csv(client, "codigo,nombre,costo\n,Sin código,-5\n").get_json()
    assert previa["con_errores"] == 1
    respuesta = client.post("/importaciones/confirmar", json={"token": previa["token"]})
    assert respuesta.status_code == 400
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Producto.id))) == 0


def test_token_de_importacion_no_cruza_empresas(app, client):
    _registrar(app, client)
    token = _csv(client, "codigo,nombre\nA-1,Empresa A\n").get_json()["token"]
    client.post("/autenticacion/salir")
    registro_b = {
        **REGISTRO,
        "empresa_nombre": "Empresa B",
        "empresa_identificacion_fiscal": "76.202.202-8",
        "identificacion_fiscal": "77.111.222-6",
        "email": "empresa-b@nexustock.cl",
    }
    _registrar(app, client, registro_b)
    respuesta = client.post("/importaciones/confirmar", json={"token": token})
    assert respuesta.status_code == 403


def test_pdf_danado_se_rechaza_sin_guardarlo(app, client):
    _registrar(app, client)
    respuesta = client.post(
        "/importaciones/previsualizar",
        data={"archivo": (BytesIO(b"no es pdf"), "lista.pdf")},
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 400


def test_centro_importacion_respeta_plan(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    assert client.get("/panel/importaciones").status_code == 403
