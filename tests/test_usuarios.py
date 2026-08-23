import pytest

from app.models import Auditoria, Empresa, Sucursal, Usuario, UsuarioSucursal, db
from app.services.usuarios import ErrorUsuario, LimiteUsuariosAlcanzado, ServicioUsuarios
from tests.test_autenticacion import REGISTRO


def _preparar(app, client, limite=10):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        admin = db.session.scalar(db.select(Usuario))
        admin.empresa.suscripcion_actual.plan.limite_usuarios = limite
        sucursal = db.session.scalar(
            db.select(Sucursal).where(Sucursal.empresa_id == admin.empresa_id)
        )
        db.session.commit()
        return admin.id, sucursal.id


def _crear(ids, **cambios):
    datos = dict(
        nombre="Empleado",
        apellido="Uno",
        email="empleado@nexustock.cl",
        password="ClaveSegura123",
        rol="empleado",
        sucursales_ids=[ids[1]],
    )
    datos.update(cambios)
    return ServicioUsuarios(db.session.get(Usuario, ids[0])).crear(**datos)


def test_crear_usuario_respeta_empresa_y_sucursal(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = _crear(ids)
        assert usuario.empresa_id == db.session.get(Usuario, ids[0]).empresa_id
        assert usuario.check_password("ClaveSegura123")
        assert [(a.sucursal_id, a.es_principal) for a in usuario.asignaciones] == [(ids[1], True)]


def test_limite_del_plan_cuenta_usuarios_activos(app, client):
    ids = _preparar(app, client, limite=1)
    with app.app_context(), pytest.raises(LimiteUsuariosAlcanzado):
        _crear(ids)


def test_no_permite_super_admin_ni_sucursal_ajena(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        with pytest.raises(ErrorUsuario):
            _crear(ids, rol="super_admin")
        otra = Empresa(nombre="Ajena", email="usuario-ajeno@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        sucursal = Sucursal(empresa_id=otra.id, codigo="AJ", nombre="Ajena")
        db.session.add(sucursal)
        db.session.commit()
        with pytest.raises(PermissionError):
            _crear(ids, email="otro@nexustock.cl", sucursales_ids=[sucursal.id])


def test_permiso_especial_no_puede_saltar_plan(app, client):
    ids = _preparar(app, client)
    with app.app_context(), pytest.raises(ErrorUsuario):
        _crear(ids, permisos_especiales={"api.gestionar": True})


def test_permiso_desconocido_y_valor_no_booleano_son_rechazados(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        with pytest.raises(ErrorUsuario):
            _crear(ids, permisos_especiales={"sistema.dios": True})
        with pytest.raises(ErrorUsuario):
            _crear(ids, permisos_especiales={"stock.salida": "sí"})


def test_editar_rol_y_permisos_revoca_sesiones(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = _crear(ids)
        version = usuario.version_sesion
        ServicioUsuarios(db.session.get(Usuario, ids[0])).editar(
            usuario.id, rol="supervisor", permisos_especiales={"stock.ajuste": False}
        )
        assert usuario.rol == "supervisor" and usuario.permisos_especiales == {
            "stock.ajuste": False
        }
        assert usuario.version_sesion == version + 1


def test_no_desactiva_propia_cuenta_ni_ultimo_admin(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioUsuarios(db.session.get(Usuario, ids[0]))
        with pytest.raises(ErrorUsuario):
            servicio.desactivar(ids[0])
        segundo = _crear(ids, email="admin2@nexustock.cl", rol="jefe")
        servicio.desactivar(segundo.id)
        assert not segundo.activo


def test_desactivar_revoca_sesion_y_reactivar_respeta_limite(app, client):
    ids = _preparar(app, client, limite=2)
    with app.app_context():
        servicio = ServicioUsuarios(db.session.get(Usuario, ids[0]))
        usuario = _crear(ids)
        version = usuario.version_sesion
        servicio.desactivar(usuario.id)
        assert not usuario.activo and usuario.version_sesion == version + 1
        servicio.reactivar(usuario.id)
        assert usuario.activo


def test_usuario_ajeno_no_es_accesible(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        otra = Empresa(nombre="Ajena", email="otra-usuarios@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        ajeno = Usuario(
            empresa_id=otra.id, nombre="Ajeno", email="ajeno-usuarios@nexustock.cl", rol="empleado"
        )
        ajeno.set_password("ClaveSegura123")
        db.session.add(ajeno)
        db.session.commit()
        with pytest.raises(PermissionError):
            ServicioUsuarios(db.session.get(Usuario, ids[0])).obtener(ajeno.id)


def test_operaciones_generan_auditoria(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        usuario = _crear(ids)
        ServicioUsuarios(db.session.get(Usuario, ids[0])).revocar_sesiones(usuario.id)
        acciones = set(
            db.session.scalars(db.select(Auditoria.accion).where(Auditoria.modulo == "usuarios"))
        )
        assert {"usuario.creado", "usuario.sesiones_revocadas"} <= acciones


def test_api_usuarios_ignora_empresa_id(app, client):
    ids = _preparar(app, client)
    respuesta = client.post(
        "/api/usuarios",
        json={
            "empresa_id": 999,
            "nombre": "API",
            "email": "api@nexustock.cl",
            "password": "ClaveSegura123",
            "rol": "empleado",
            "sucursales_ids": [ids[1]],
        },
    )
    assert respuesta.status_code == 201
    with app.app_context():
        creado = db.session.scalar(db.select(Usuario).where(Usuario.email == "api@nexustock.cl"))
        assert creado.empresa_id == db.session.get(Usuario, ids[0]).empresa_id
