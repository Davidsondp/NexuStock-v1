from io import BytesIO
from zipfile import ZipFile

import pytest

from app.models import Auditoria, Bodega, Empresa, Producto, Usuario, db
from app.services.exportaciones import ErrorExportacion, ServicioExportaciones
from app.services.reportes import construir_periodo
from tests.test_reportes import _preparar


def _habilitar(app, ids):
    with app.app_context():
        usuario = db.session.get(Usuario, ids[0])
        plan = usuario.empresa.suscripcion_actual.plan
        plan.funciones = {**plan.funciones, "exportacion.avanzada": True}
        db.session.commit()


def test_csv_stock_incluye_bom_y_separador_chileno(app, client):
    ids = _preparar(app, client)
    _habilitar(app, ids)
    respuesta = client.get("/api/reportes/exportar/stock.csv")
    texto = respuesta.data.decode("utf-8-sig")
    assert respuesta.status_code == 200
    assert "nexustock_stock_" in respuesta.headers["Content-Disposition"]
    assert respuesta.headers["Content-Disposition"].endswith(".csv")
    assert texto.startswith("Código;Producto;Bodega;Cantidad")
    assert "Más vendido" in texto


def test_xlsx_es_paquete_open_xml_valido(app, client):
    ids = _preparar(app, client)
    _habilitar(app, ids)
    respuesta = client.get("/api/reportes/exportar/productos.xlsx")
    assert respuesta.status_code == 200
    with ZipFile(BytesIO(respuesta.data)) as archivo:
        nombres = set(archivo.namelist())
        assert {"[Content_Types].xml", "xl/workbook.xml", "xl/worksheets/sheet1.xml"} <= nombres
        hoja = archivo.read("xl/worksheets/sheet1.xml").decode()
        assert "Más vendido" in hoja and "<autoFilter" in hoja


def test_neutraliza_inyeccion_de_formulas_csv_y_excel(app, client):
    ids = _preparar(app, client)
    _habilitar(app, ids)
    with app.app_context():
        producto = db.session.get(Producto, ids[2])
        producto.nombre = '=HIPERVINCULO("sitio")'
        db.session.commit()
    csv_respuesta = client.get("/api/reportes/exportar/productos.csv")
    assert "'=HIPERVINCULO" in csv_respuesta.data.decode("utf-8-sig")
    xlsx_respuesta = client.get("/api/reportes/exportar/productos.xlsx")
    with ZipFile(BytesIO(xlsx_respuesta.data)) as archivo:
        hoja = archivo.read("xl/worksheets/sheet1.xml").decode()
        assert "'=HIPERVINCULO" in hoja and "<f>" not in hoja


def test_exportacion_exige_funcion_del_plan(app, client):
    _preparar(app, client)
    respuesta = client.get("/api/reportes/exportar/stock.csv")
    assert respuesta.status_code == 403
    assert respuesta.get_json()["codigo"] == "plan_insuficiente"


def test_formato_y_reporte_no_permitidos_se_rechazan(app, client):
    ids = _preparar(app, client)
    _habilitar(app, ids)
    assert client.get("/api/reportes/exportar/usuarios.csv").status_code == 400
    assert client.get("/api/reportes/exportar/stock.pdf").status_code == 400


def test_no_exporta_bodega_ajena(app, client):
    ids = _preparar(app, client)
    _habilitar(app, ids)
    with app.app_context():
        otra = Empresa(nombre="Ajena", email="exportacion-ajena@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        from app.models import Sucursal

        sucursal = Sucursal(empresa_id=otra.id, codigo="AJ", nombre="Ajena")
        db.session.add(sucursal)
        db.session.flush()
        bodega = Bodega(empresa_id=otra.id, sucursal_id=sucursal.id, codigo="AJ", nombre="Ajena")
        db.session.add(bodega)
        db.session.commit()
        bodega_id = bodega.id
    assert client.get(f"/api/reportes/exportar/stock.csv?bodega_id={bodega_id}").status_code == 403


def test_exportacion_registra_auditoria(app, client):
    ids = _preparar(app, client)
    _habilitar(app, ids)
    client.get("/api/reportes/exportar/movimientos.csv")
    with app.app_context():
        auditoria = db.session.scalar(
            db.select(Auditoria).where(Auditoria.accion == "reporte.exportado")
        )
        assert auditoria and auditoria.datos_nuevos["reporte"] == "movimientos"


def test_servicio_no_acepta_extension_arbitraria(app, client):
    ids = _preparar(app, client)
    _habilitar(app, ids)
    with app.app_context(), pytest.raises(ErrorExportacion):
        ServicioExportaciones(db.session.get(Usuario, ids[0])).exportar(
            "stock", "html", periodo=construir_periodo()
        )
