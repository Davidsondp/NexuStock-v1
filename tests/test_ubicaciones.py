import pytest

from app.models import Bodega, Empresa, Inventario, Sucursal, Usuario, UsuarioSucursal, db
from app.services.ubicaciones import (
    ErrorUbicacion,
    LimiteBodegasAlcanzado,
    LimiteSucursalesAlcanzado,
    ServicioUbicaciones,
)
from tests.test_autenticacion import REGISTRO


def _preparar(app, client, funciones=True):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        plan = usuario.empresa.suscripcion_actual.plan
        plan.limite_sucursales = None
        plan.limite_bodegas = None
        if funciones:
            plan.funciones = {**plan.funciones, "multisucursal": True, "multibodega": True}
        db.session.commit()
        return usuario.id


def test_crear_sucursal_crea_bodega_y_asigna_creador(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        sucursal = ServicioUbicaciones(db.session.get(Usuario, usuario_id)).crear_sucursal(
            codigo="NORTE", nombre="Sucursal Norte"
        )
        assert len(sucursal.bodegas) == 1
        assert (
            db.session.scalar(
                db.select(db.func.count(UsuarioSucursal.id)).where(
                    UsuarioSucursal.sucursal_id == sucursal.id,
                    UsuarioSucursal.usuario_id == usuario_id,
                )
            )
            == 1
        )


def test_limite_sucursales_y_bodegas(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        plan = usuario.empresa.suscripcion_actual.plan
        plan.limite_sucursales = 1
        plan.limite_bodegas = 1
        db.session.commit()
        servicio = ServicioUbicaciones(usuario)
        with pytest.raises(LimiteSucursalesAlcanzado):
            servicio.crear_sucursal(codigo="DOS", nombre="Dos")
        principal = db.session.scalar(db.select(Sucursal))
        with pytest.raises(LimiteBodegasAlcanzado):
            servicio.crear_bodega(sucursal_id=principal.id, codigo="DOS", nombre="Dos")


def test_plan_sin_multisucursal_rechaza_creacion(app, client):
    usuario_id = _preparar(app, client, funciones=False)
    with app.app_context(), pytest.raises(PermissionError):
        ServicioUbicaciones(db.session.get(Usuario, usuario_id)).crear_sucursal(
            codigo="DOS", nombre="Dos"
        )


def test_no_desactiva_ultima_sucursal_o_bodega(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        servicio = ServicioUbicaciones(db.session.get(Usuario, usuario_id))
        sucursal = db.session.scalar(db.select(Sucursal))
        bodega = db.session.scalar(db.select(Bodega))
        with pytest.raises(ErrorUbicacion):
            servicio.desactivar_sucursal(sucursal.id)
        with pytest.raises(ErrorUbicacion):
            servicio.desactivar_bodega(bodega.id)


def test_no_desactiva_bodega_con_stock(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        from app.models import Producto

        usuario = db.session.get(Usuario, usuario_id)
        servicio = ServicioUbicaciones(usuario)
        sucursal = db.session.scalar(db.select(Sucursal))
        bodega = servicio.crear_bodega(sucursal_id=sucursal.id, codigo="DOS", nombre="Dos")
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="P",
            nombre="P",
            costo_referencia=0,
            precio_venta=0,
        )
        db.session.add(producto)
        db.session.flush()
        db.session.add(
            Inventario(
                empresa_id=usuario.empresa_id,
                bodega_id=bodega.id,
                producto_id=producto.id,
                cantidad=1,
                cantidad_reservada=0,
                costo_promedio=0,
            )
        )
        db.session.commit()
        with pytest.raises(ErrorUbicacion):
            servicio.desactivar_bodega(bodega.id)


def test_asignacion_ajena_es_rechazada(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        admin = db.session.get(Usuario, usuario_id)
        otra = Empresa(nombre="Ajena", email="ajena-ubicacion@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        ajeno = Usuario(
            empresa_id=otra.id, nombre="Ajeno", email="ajeno@ubicacion.cl", rol="empleado"
        )
        ajeno.set_password("ClaveAjena123")
        db.session.add(ajeno)
        db.session.commit()
        ajeno_id = ajeno.id
        sucursal = db.session.scalar(
            db.select(Sucursal).where(Sucursal.empresa_id == admin.empresa_id)
        )
        with pytest.raises(PermissionError):
            ServicioUbicaciones(admin).asignar_usuario(usuario_id=ajeno_id, sucursal_id=sucursal.id)


def test_desasignacion_conserva_una_sucursal(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        servicio = ServicioUbicaciones(usuario)
        principal = db.session.scalar(db.select(Sucursal))
        with pytest.raises(ErrorUbicacion):
            servicio.desasignar_usuario(usuario_id=usuario.id, sucursal_id=principal.id)


def test_api_ignora_empresa_id_y_protege_idor(app, client):
    usuario_id = _preparar(app, client)
    respuesta = client.post(
        "/api/sucursales",
        json={
            "empresa_id": 999,
            "codigo": "API",
            "nombre": "Desde API",
            "crear_bodega_principal": False,
        },
    )
    assert respuesta.status_code == 201
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        sucursal = db.session.scalar(db.select(Sucursal).where(Sucursal.codigo == "API"))
        assert sucursal.empresa_id == usuario.empresa_id
        otra = Empresa(nombre="Otra", email="otra-ubicacion-api@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        ajena = Sucursal(empresa_id=otra.id, codigo="AJENA", nombre="Ajena")
        db.session.add(ajena)
        db.session.commit()
        ajena_id = ajena.id
    assert client.delete(f"/api/sucursales/{ajena_id}").status_code == 403


def test_api_lista_ubicaciones_inactivas_y_detalles(
    app,
    client,
):
    usuario_id = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        servicio = ServicioUbicaciones(usuario)

        sucursal = servicio.crear_sucursal(
            codigo="SUR",
            nombre="Sucursal Sur",
            direccion="Calle Uno 123",
            ciudad="Santiago",
            telefono="221234567",
        )

        bodega = sucursal.bodegas[0]
        bodega.descripcion = "Despacho mayorista"
        db.session.commit()

        bodega_id = bodega.id

        servicio.desactivar_sucursal(sucursal.id)

    respuesta = client.get("/api/sucursales" "?incluir_inactivas=true")

    assert respuesta.status_code == 200

    sucursales = respuesta.get_json()["sucursales"]

    encontrada = next(item for item in sucursales if item["codigo"] == "SUR")

    assert encontrada["nombre"] == "Sucursal Sur"
    assert encontrada["direccion"] == "Calle Uno 123"
    assert encontrada["ciudad"] == "Santiago"
    assert encontrada["telefono"] == "221234567"
    assert encontrada["activa"] is False

    respuesta = client.get("/api/bodegas" "?incluir_inactivas=true")

    assert respuesta.status_code == 200

    bodegas = respuesta.get_json()["bodegas"]

    encontrada = next(item for item in bodegas if item["id"] == bodega_id)

    assert encontrada["descripcion"] == ("Despacho mayorista")
    assert encontrada["activa"] is False


def test_api_edita_sucursal_y_bodega(
    app,
    client,
):
    _preparar(app, client)

    sucursal = client.post(
        "/api/sucursales",
        json={
            "codigo": "NORTE",
            "nombre": "Sucursal Norte",
            "crear_bodega_principal": False,
        },
    ).get_json()

    respuesta = client.patch(
        f"/api/sucursales/{sucursal['id']}",
        json={
            "codigo": "NORTE-2",
            "nombre": "Sucursal Norte Dos",
            "direccion": "Avenida Dos 456",
            "ciudad": "Providencia",
            "telefono": "229876543",
            "empresa_id": 999999,
        },
    )

    assert respuesta.status_code == 200

    datos = respuesta.get_json()

    assert datos["codigo"] == "NORTE-2"
    assert datos["nombre"] == ("Sucursal Norte Dos")
    assert datos["direccion"] == ("Avenida Dos 456")
    assert datos["ciudad"] == "Providencia"
    assert datos["telefono"] == "229876543"

    bodega = client.post(
        "/api/bodegas",
        json={
            "sucursal_id": sucursal["id"],
            "codigo": "BOD-NORTE",
            "nombre": "Bodega Norte",
        },
    ).get_json()

    respuesta = client.patch(
        f"/api/bodegas/{bodega['id']}",
        json={
            "codigo": "BOD-NORTE-2",
            "nombre": "Bodega Norte Dos",
            "descripcion": "Recepcion y despacho",
            "sucursal_id": 999999,
            "empresa_id": 999999,
        },
    )

    assert respuesta.status_code == 200

    datos = respuesta.get_json()

    assert datos["codigo"] == "BOD-NORTE-2"
    assert datos["nombre"] == "Bodega Norte Dos"
    assert datos["descripcion"] == ("Recepcion y despacho")
    assert datos["sucursal_id"] == sucursal["id"]


def test_api_reactiva_sucursal_y_bodega(
    app,
    client,
):
    usuario_id = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        servicio = ServicioUbicaciones(usuario)

        sucursal = servicio.crear_sucursal(
            codigo="REACT",
            nombre="Sucursal Reactivable",
        )
        sucursal_id = sucursal.id
        bodega_id = sucursal.bodegas[0].id

        servicio.desactivar_sucursal(sucursal_id)

    respuesta = client.post(f"/api/sucursales/{sucursal_id}" "/reactivar")

    assert respuesta.status_code == 200
    assert respuesta.get_json()["activa"] is True

    respuesta = client.get("/api/bodegas" "?incluir_inactivas=true")

    bodega = next(item for item in respuesta.get_json()["bodegas"] if item["id"] == bodega_id)

    assert bodega["activa"] is True

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        servicio = ServicioUbicaciones(usuario)

        servicio.crear_bodega(
            sucursal_id=sucursal_id,
            codigo="REACT-2",
            nombre="Bodega Reactivable",
        )

        bodega = db.session.scalar(db.select(Bodega).where(Bodega.codigo == "REACT-2"))

        servicio.desactivar_bodega(bodega.id)
        segundo_id = bodega.id

    respuesta = client.post(f"/api/bodegas/{segundo_id}" "/reactivar")

    assert respuesta.status_code == 200
    assert respuesta.get_json()["activa"] is True


def test_api_desasigna_usuario_de_sucursal(
    app,
    client,
):
    usuario_id = _preparar(app, client)

    with app.app_context():
        admin = db.session.get(
            Usuario,
            usuario_id,
        )
        servicio = ServicioUbicaciones(admin)

        segunda = servicio.crear_sucursal(
            codigo="USUARIOS",
            nombre="Sucursal Usuarios",
        )

        empleado = Usuario(
            empresa_id=admin.empresa_id,
            nombre="Empleado",
            apellido="Asignado",
            email="asignado.ubicacion@nexustock.cl",
            rol="empleado",
            activo=True,
        )
        empleado.set_password("ClaveEmpleado123")

        db.session.add(empleado)
        db.session.flush()

        principal = db.session.scalar(
            db.select(Sucursal).where(
                Sucursal.empresa_id == admin.empresa_id,
                Sucursal.codigo == "PRINCIPAL",
            )
        )

        db.session.add_all(
            [
                UsuarioSucursal(
                    empresa_id=admin.empresa_id,
                    usuario_id=empleado.id,
                    sucursal_id=principal.id,
                    es_principal=True,
                ),
                UsuarioSucursal(
                    empresa_id=admin.empresa_id,
                    usuario_id=empleado.id,
                    sucursal_id=segunda.id,
                    es_principal=False,
                ),
            ]
        )
        db.session.commit()

        empleado_id = empleado.id
        segunda_id = segunda.id

    respuesta = client.delete(f"/api/sucursales/{segunda_id}" f"/usuarios/{empleado_id}")

    assert respuesta.status_code == 204

    with app.app_context():
        asignacion = db.session.scalar(
            db.select(UsuarioSucursal).where(
                UsuarioSucursal.usuario_id == empleado_id,
                UsuarioSucursal.sucursal_id == segunda_id,
            )
        )

        assert asignacion is None


def test_api_ubicaciones_rechaza_edicion_ajena(
    app,
    client,
):
    _preparar(app, client)

    with app.app_context():
        otra = Empresa(
            nombre="Empresa Ajena",
            email="empresa.ajena.edicion@nexustock.cl",
        )
        db.session.add(otra)
        db.session.flush()

        sucursal = Sucursal(
            empresa_id=otra.id,
            codigo="AJENA-EDIT",
            nombre="Sucursal Ajena",
        )
        db.session.add(sucursal)
        db.session.flush()

        bodega = Bodega(
            empresa_id=otra.id,
            sucursal_id=sucursal.id,
            codigo="AJENA-EDIT",
            nombre="Bodega Ajena",
        )
        db.session.add(bodega)
        db.session.commit()

        sucursal_id = sucursal.id
        bodega_id = bodega.id

    respuesta = client.patch(
        f"/api/sucursales/{sucursal_id}",
        json={"nombre": "Alterada"},
    )

    assert respuesta.status_code == 403

    respuesta = client.patch(
        f"/api/bodegas/{bodega_id}",
        json={"nombre": "Alterada"},
    )

    assert respuesta.status_code == 403
