from app.models import ConfiguracionEmpresa, Usuario, UsuarioSucursal, db
from tests.test_autenticacion import REGISTRO


def registrar_empresa(client):
    return client.post(
        "/autenticacion/registro",
        data=REGISTRO,
    )


def configurar_rubro(client, rubro):
    registrar_empresa(client)

    with client.application.app_context():
        configuracion = db.session.scalar(db.select(ConfiguracionEmpresa))
        configuracion.opciones = {
            "rubro": rubro,
            "capacidades": {},
        }
        db.session.commit()


def crear_superadmin(app):
    with app.app_context():
        usuario = Usuario(
            empresa_id=None,
            nombre="Super",
            apellido="Administrador",
            email="productos.global@nexustock.cl",
            rol="super_admin",
            activo=True,
        )
        usuario.set_password("ClaveSuperAdmin123")
        db.session.add(usuario)
        db.session.commit()


def iniciar_superadmin(client):
    return client.post(
        "/autenticacion/ingresar",
        data={
            "email": "productos.global@nexustock.cl",
            "password": "ClaveSuperAdmin123",
        },
    )


def test_panel_productos_exige_autenticacion(client):
    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_usuario_empresarial_puede_ver_productos(app, client):
    registrar_empresa(client)

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200
    assert "Productos".encode("utf-8") in respuesta.data
    assert REGISTRO["empresa_nombre"].encode("utf-8") in respuesta.data


def test_superadmin_no_accede_a_productos_empresariales(app, client):
    crear_superadmin(app)
    iniciar_superadmin(client)

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 403


def test_panel_empresarial_enlaza_modulo_productos(client):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    assert b"/panel/productos" in respuesta.data


def test_pagina_productos_referencia_api_empresarial(app, client):
    registrar_empresa(client)

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200
    assert b"/api/productos" in respuesta.data
    assert b"/api/proveedores" in respuesta.data
    assert b"js/productos_presentaciones.js" in respuesta.data
    assert b'id="producto-proveedor"' in respuesta.data
    assert b"Sin proveedor asignado" in respuesta.data


def test_catalogo_incluye_consulta_movil_y_colecciones(client):
    registrar_empresa(client)

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200
    assert b'id="escanear-producto"' in respuesta.data
    assert b'id="modal-escaner"' in respuesta.data
    assert b'id="categorias-productos"' in respuesta.data
    assert b"js/escaner_productos.js" in respuesta.data
    assert b'id="producto-campos-personalizados"' in respuesta.data
    assert b"manifest.webmanifest" in respuesta.data
    assert b"js/pwa.js" in respuesta.data


def test_recursos_pwa_son_publicos_y_no_cachean_el_service_worker(client):
    manifiesto = client.get("/manifest.webmanifest")
    worker = client.get("/service-worker.js")

    assert manifiesto.status_code == 200
    assert manifiesto.get_json()["short_name"] == "NexuStock"
    assert worker.status_code == 200
    assert worker.headers["Service-Worker-Allowed"] == "/"
    assert worker.headers["Cache-Control"] in {"no-cache", "no-store"}


def test_empleado_no_ve_acciones_de_escritura(app, client):
    registrar_empresa(client)

    with app.app_context():
        administrador = db.session.scalar(
            db.select(Usuario).where(Usuario.email == REGISTRO["email"])
        )

        empleado = Usuario(
            empresa_id=administrador.empresa_id,
            nombre="Empleado",
            apellido="Consulta",
            email="empleado.productos@nexustock.cl",
            rol="empleado",
            activo=True,
        )
        empleado.set_password("ClaveEmpleado123")

        db.session.add(empleado)
        db.session.flush()

        asignacion_principal = db.session.scalar(
            db.select(UsuarioSucursal).where(
                UsuarioSucursal.empresa_id == administrador.empresa_id,
                UsuarioSucursal.usuario_id == administrador.id,
                UsuarioSucursal.es_principal.is_(True),
            )
        )
        db.session.add(
            UsuarioSucursal(
                empresa_id=administrador.empresa_id,
                usuario_id=empleado.id,
                sucursal_id=asignacion_principal.sucursal_id,
                es_principal=True,
            )
        )

        db.session.commit()

    client.post("/autenticacion/salir")

    client.post(
        "/autenticacion/ingresar",
        data={
            "email": "empleado.productos@nexustock.cl",
            "password": "ClaveEmpleado123",
        },
    )

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200
    assert b'data-permiso-crear="false"' in respuesta.data
    assert b'data-permiso-editar="false"' in respuesta.data
    assert b'data-permiso-eliminar="false"' in respuesta.data


def test_panel_general_oculta_control_de_lotes(
    client,
):
    configurar_rubro(
        client,
        "general",
    )

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200
    assert b'id="producto-controla-lotes"' not in respuesta.data
    assert b'id="producto-controla-vencimiento"' not in respuesta.data


def test_panel_minimarket_muestra_trazabilidad(
    client,
):
    configurar_rubro(
        client,
        "minimarket",
    )

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200
    assert b'id="producto-controla-lotes"' in respuesta.data
    assert b'id="producto-controla-vencimiento"' in respuesta.data


def test_farmacia_recibe_unidades_sugeridas(
    client,
):
    configurar_rubro(
        client,
        "farmacia",
    )

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200
    assert b'id="unidades-medida-sugeridas"' in respuesta.data
    assert b'value="comprimido"' in respuesta.data
    assert b'value="capsula"' in respuesta.data
    assert b'value="mililitro"' in respuesta.data


def test_botilleria_sugiere_unidades_de_bebidas(
    client,
):
    configurar_rubro(
        client,
        "botilleria",
    )

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200
    assert b'value="litro"' in respuesta.data
    assert b'value="mililitro"' in respuesta.data
    assert b'value="metro"' not in respuesta.data


def test_ferreteria_sugiere_unidades_tecnicas(
    client,
):
    configurar_rubro(
        client,
        "ferreteria",
    )

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200
    assert b'value="pieza"' in respuesta.data
    assert b'value="metro"' in respuesta.data
    assert b'value="centimetro"' in respuesta.data
    assert b'value="comprimido"' not in respuesta.data


def test_unidad_medida_permanece_editable(
    client,
):
    configurar_rubro(
        client,
        "general",
    )

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200
    assert b'id="producto-unidad-medida"' in respuesta.data
    assert b'list="unidades-medida-sugeridas"' in respuesta.data
    assert b'name="unidad_medida"' in respuesta.data


def test_panel_productos_incluye_gestion_presentaciones(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200

    identificadores = (
        b'id="seccion-presentaciones-producto"',
        b'id="lista-presentaciones-producto"',
        b'id="formulario-presentacion-producto"',
        b'id="presentacion-id"',
        b'id="presentacion-codigo"',
        b'id="presentacion-nombre"',
        b'id="presentacion-abreviatura"',
        b'id="presentacion-factor"',
        b'id="guardar-presentacion-producto"',
        b'id="cancelar-presentacion-producto"',
    )

    for identificador in identificadores:
        assert identificador in respuesta.data


def test_panel_presentaciones_explica_conversion_base(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/productos")

    assert respuesta.status_code == 200
    assert "Presentaciones de compra y venta".encode("utf-8") in respuesta.data
    assert "se convierte a la unidad base".encode("utf-8") in respuesta.data
    assert "Guarda primero el producto".encode("utf-8") in respuesta.data
