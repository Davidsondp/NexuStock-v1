from app.models import (
    ConfiguracionEmpresa,
    Usuario,
    UsuarioSucursal,
    db,
)
from tests.test_autenticacion import REGISTRO


def registrar_empresa(client):
    return client.post(
        "/autenticacion/registro",
        data=REGISTRO,
    )


def configurar_perfil_empresa(
    client,
    rubro,
    capacidades=None,
):
    registrar_empresa(client)

    with client.application.app_context():
        configuracion = db.session.scalar(db.select(ConfiguracionEmpresa))
        configuracion.opciones = {
            "rubro": rubro,
            "capacidades": capacidades or {},
        }
        db.session.commit()


def crear_superadmin(app):
    with app.app_context():
        usuario = Usuario(
            empresa_id=None,
            nombre="Super",
            apellido="Administrador",
            email="inventario.global@nexustock.cl",
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
            "email": "inventario.global@nexustock.cl",
            "password": "ClaveSuperAdmin123",
        },
    )


def test_panel_inventario_exige_autenticacion(
    client,
):
    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_usuario_empresarial_puede_ver_inventario(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 200
    assert "Inventario".encode("utf-8") in respuesta.data
    assert REGISTRO["empresa_nombre"].encode("utf-8") in respuesta.data


def test_superadmin_no_accede_a_inventario_empresarial(
    app,
    client,
):
    crear_superadmin(app)
    iniciar_superadmin(client)

    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 403


def test_panel_empresarial_enlaza_inventario(client):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    assert b"/panel/inventario" in respuesta.data


def test_pagina_inventario_referencia_apis_y_recursos(
    client,
):
    configurar_perfil_empresa(
        client,
        "farmacia",
    )

    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 200
    assert b"/api/inventario/movimientos" in respuesta.data
    assert b"/api/inventario/stock" in respuesta.data
    assert b"/api/inventario/lotes" in respuesta.data
    assert b"/api/inventario/movimientos" in respuesta.data
    assert b"/api/productos" in respuesta.data
    assert b"css/panel_empresarial.css" in respuesta.data
    assert b"css/inventario.css" in respuesta.data
    assert b"js/inventario.js" in respuesta.data
    assert b'id="resumen-inventario"' in respuesta.data
    assert b'id="buscar-inventario"' in respuesta.data
    assert b'id="tabla-stock"' in respuesta.data
    assert b'id="tabla-movimientos"' in respuesta.data
    assert b'id="resumen-lotes"' in respuesta.data
    assert b'id="filtrar-vencimiento"' in respuesta.data
    assert b'id="tabla-lotes"' in respuesta.data
    assert b'id="nuevo-movimiento"' in respuesta.data
    assert b'id="modal-movimiento"' in respuesta.data
    assert b'id="formulario-movimiento"' in respuesta.data
    assert b'id="movimiento-tipo"' in respuesta.data
    assert b'id="movimiento-producto"' in respuesta.data
    assert b'id="movimiento-cantidad"' in respuesta.data
    assert b'id="movimiento-stock-final"' in respuesta.data
    assert b'id="movimiento-costo-unitario"' in respuesta.data
    assert b'id="movimiento-precio-unitario"' in respuesta.data
    assert b'id="movimiento-motivo"' in respuesta.data
    assert b'id="grupo-numero-lote"' in respuesta.data
    assert b'id="movimiento-numero-lote"' in respuesta.data
    assert b'id="grupo-fecha-vencimiento"' in respuesta.data
    assert b'id="movimiento-fecha-vencimiento"' in respuesta.data
    assert b'id="ayuda-trazabilidad"' in respuesta.data
    assert b' name="csrf_token"' in respuesta.data


def test_empleado_conserva_operaciones_autorizadas(
    app,
    client,
):
    registrar_empresa(client)

    with app.app_context():
        administrador = db.session.scalar(
            db.select(Usuario).where(Usuario.email == REGISTRO["email"])
        )

        empleado = Usuario(
            empresa_id=administrador.empresa_id,
            nombre="Empleado",
            apellido="Inventario",
            email="empleado.inventario@nexustock.cl",
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
            "email": "empleado.inventario@nexustock.cl",
            "password": "ClaveEmpleado123",
        },
    )

    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 200
    assert b'data-permiso-entrada="true"' in respuesta.data
    assert b'data-permiso-salida="true"' in respuesta.data
    assert b'data-permiso-ajuste="false"' in respuesta.data
    assert b'data-permiso-devolucion="true"' in respuesta.data


def test_panel_muestra_un_solo_enlace_inventario(
    client,
):
    registrar_empresa(client)

    respuesta = client.get("/panel")

    assert respuesta.status_code == 200
    navegacion = respuesta.data.split(b'<nav class="navegacion"', 1)[1].split(b"</nav>", 1)[0]
    assert navegacion.count(b'href="/panel/inventario"') == 1


def test_panel_inventario_incluye_escaner_movil(client):
    registrar_empresa(client)

    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 200
    assert b'id="abrir-escaner"' in respuesta.data
    assert b'id="video-escaner"' in respuesta.data
    assert b'id="codigo-escaneado-manual"' in respuesta.data
    assert b"Escanear QR o c\xc3\xb3digo de barras" in respuesta.data


def test_empresa_general_oculta_inventario_farmaceutico(
    client,
):
    configurar_perfil_empresa(
        client,
        "general",
    )

    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 200
    assert b"/api/inventario/lotes" not in respuesta.data
    assert b'id="tabla-lotes"' not in respuesta.data


def test_farmacia_muestra_inventario_farmaceutico(
    client,
):
    configurar_perfil_empresa(
        client,
        "farmacia",
    )

    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 200
    assert b"/api/inventario/lotes" in respuesta.data
    assert b'id="tabla-lotes"' in respuesta.data


def test_botilleria_muestra_control_de_lotes(
    client,
):
    configurar_perfil_empresa(
        client,
        "botilleria",
    )

    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 200
    assert b"/api/inventario/lotes" in respuesta.data
    assert b'id="tabla-lotes"' in respuesta.data


def test_capacidad_explicita_habilita_inventario_farmaceutico(
    client,
):
    configurar_perfil_empresa(
        client,
        "general",
        {
            "inventario_farmaceutico": True,
        },
    )

    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 200
    assert b"/api/inventario/lotes" in respuesta.data
    assert b'id="tabla-lotes"' in respuesta.data


def test_minimarket_muestra_control_de_lotes(
    client,
):
    configurar_perfil_empresa(
        client,
        "minimarket",
    )

    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 200
    assert b"/api/inventario/lotes" in respuesta.data
    assert b'id="tabla-lotes"' in respuesta.data


def test_ferreteria_oculta_control_de_lotes(
    client,
):
    configurar_perfil_empresa(
        client,
        "ferreteria",
    )

    respuesta = client.get("/panel/inventario")

    assert respuesta.status_code == 200
    assert b"/api/inventario/lotes" not in respuesta.data
    assert b'id="tabla-lotes"' not in respuesta.data
