from app.models import Auditoria, Empresa, Usuario, db
from app.services.auditoria import ServicioAuditoriaEmpresa, registrar_auditoria
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        usuario.empresa.suscripcion_actual.plan.funciones = {
            **usuario.empresa.suscripcion_actual.plan.funciones,
            "auditoria": True,
        }
        registrar_auditoria(
            accion="producto.prueba",
            modulo="productos",
            usuario_id=usuario.id,
            empresa_id=usuario.empresa_id,
            entidad_tipo="Producto",
            entidad_id=7,
            datos_nuevos={"nombre": "Seguro"},
        )
        db.session.commit()
        return usuario.id


def test_auditoria_empresa_filtra_y_no_expone_otra_empresa(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        actor = db.session.get(Usuario, usuario_id)
        ajena = Empresa(nombre="Ajena", email="audit-ajena@nexustock.cl")
        db.session.add(ajena)
        db.session.flush()
        registrar_auditoria(accion="ajena", modulo="productos", empresa_id=ajena.id)
        db.session.commit()
        registros = ServicioAuditoriaEmpresa(actor).listar(modulo="productos")
        assert {r.empresa_id for r in registros} == {actor.empresa_id}
        assert all(isinstance(r, Auditoria) for r in registros)


def test_api_panel_y_exportacion_auditoria(app, client):
    _preparar(app, client)
    respuesta = client.get("/api/auditoria?modulo=productos")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["auditoria"][0]["accion"] == "producto.prueba"
    assert client.get("/panel/administracion/auditoria").status_code == 200
    csv = client.get("/api/auditoria/exportar.csv?modulo=productos")
    assert csv.status_code == 200
    assert "producto.prueba" in csv.get_data(as_text=True)
