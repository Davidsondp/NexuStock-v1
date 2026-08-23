from tests.test_autenticacion import REGISTRO


def registrar_empresa(client):
    return client.post(
        "/autenticacion/registro",
        data=REGISTRO,
    )


def test_api_clientes_exige_autenticacion(client):
    respuesta = client.get("/api/clientes")

    assert respuesta.status_code == 302
    assert "/autenticacion/ingresar" in respuesta.location


def test_api_crea_y_lista_cliente(client):
    registrar_empresa(client)

    respuesta_creacion = client.post(
        "/api/clientes",
        json={
            "nombre": "Farmacia Cliente",
            "identificacion_fiscal": "12.345.678-5",
            "email": "cliente@farmacia.cl",
            "telefono": "+56912345678",
            "direccion": "Avenida Central 123",
        },
    )

    assert respuesta_creacion.status_code == 201

    cliente = respuesta_creacion.get_json()

    campos_esperados = {
        "id",
        "nombre",
        "identificacion_fiscal",
        "email",
        "telefono",
        "direccion",
        "activo",
    }

    assert campos_esperados.issubset(cliente)
    assert cliente["nombre"] == "Farmacia Cliente"
    assert cliente["activo"] is True

    respuesta_listado = client.get("/api/clientes")

    assert respuesta_listado.status_code == 200

    clientes = respuesta_listado.get_json()["clientes"]

    assert len(clientes) == 1
    assert clientes[0]["id"] == cliente["id"]


def test_api_edita_cliente(client):
    registrar_empresa(client)

    creacion = client.post(
        "/api/clientes",
        json={
            "nombre": "Cliente Original",
            "identificacion_fiscal": "11.111.111-1",
        },
    )

    assert creacion.status_code == 201

    cliente_id = creacion.get_json()["id"]

    edicion = client.patch(
        f"/api/clientes/{cliente_id}",
        json={
            "nombre": "Cliente Actualizado",
            "email": "actualizado@nexustock.cl",
            "telefono": "+56987654321",
            "direccion": "Nueva dirección 456",
        },
    )

    assert edicion.status_code == 200

    cliente = edicion.get_json()

    assert cliente["nombre"] == "Cliente Actualizado"
    assert cliente["email"] == "actualizado@nexustock.cl"
    assert cliente["telefono"] == "+56987654321"
    assert cliente["direccion"] == "Nueva dirección 456"


def test_api_busca_desactiva_y_reactiva_cliente(client):
    registrar_empresa(client)

    respuesta_principal = client.post(
        "/api/clientes",
        json={
            "nombre": "Paciente Austral",
            "identificacion_fiscal": "22.222.222-2",
            "email": "austral@nexustock.cl",
        },
    )

    respuesta_secundaria = client.post(
        "/api/clientes",
        json={
            "nombre": "Cliente Central",
            "identificacion_fiscal": "33.333.333-3",
            "email": "central@nexustock.cl",
        },
    )

    assert respuesta_principal.status_code == 201
    assert respuesta_secundaria.status_code == 201

    cliente_id = respuesta_principal.get_json()["id"]

    respuesta_busqueda = client.get("/api/clientes?buscar=Austral")

    assert respuesta_busqueda.status_code == 200

    nombres = {cliente["nombre"] for cliente in respuesta_busqueda.get_json()["clientes"]}

    assert nombres == {"Paciente Austral"}

    desactivacion = client.post(f"/api/clientes/{cliente_id}/desactivar")

    assert desactivacion.status_code == 200
    assert desactivacion.get_json()["activo"] is False

    listado_activos = client.get("/api/clientes")

    ids_activos = {cliente["id"] for cliente in listado_activos.get_json()["clientes"]}

    assert cliente_id not in ids_activos

    listado_completo = client.get("/api/clientes?incluir_inactivos=true")

    clientes = listado_completo.get_json()["clientes"]

    cliente_inactivo = next(cliente for cliente in clientes if cliente["id"] == cliente_id)

    assert cliente_inactivo["activo"] is False

    reactivacion = client.post(f"/api/clientes/{cliente_id}/reactivar")

    assert reactivacion.status_code == 200
    assert reactivacion.get_json()["activo"] is True


def test_api_rechaza_cliente_invalido_y_rut_duplicado(
    client,
):
    registrar_empresa(client)

    respuesta_sin_nombre = client.post(
        "/api/clientes",
        json={
            "nombre": "   ",
            "identificacion_fiscal": "44.444.444-4",
        },
    )

    assert respuesta_sin_nombre.status_code == 400
    assert respuesta_sin_nombre.get_json()["codigo"] == "cliente_invalido"

    primera_creacion = client.post(
        "/api/clientes",
        json={
            "nombre": "Cliente Principal",
            "identificacion_fiscal": "44.444.444-4",
        },
    )

    assert primera_creacion.status_code == 201

    duplicado = client.post(
        "/api/clientes",
        json={
            "nombre": "Cliente Duplicado",
            "identificacion_fiscal": "44.444.444-4",
        },
    )

    assert duplicado.status_code == 400
    assert duplicado.get_json()["codigo"] == "cliente_invalido"


def test_api_elimina_cliente_sin_historial(client):
    registrar_empresa(client)

    creacion = client.post(
        "/api/clientes",
        json={
            "nombre": "Cliente Eliminable",
            "identificacion_fiscal": "55.555.555-5",
        },
    )

    assert creacion.status_code == 201

    cliente_id = creacion.get_json()["id"]

    eliminacion = client.delete(f"/api/clientes/{cliente_id}")

    assert eliminacion.status_code == 204

    listado = client.get("/api/clientes?incluir_inactivos=true")

    ids = {cliente["id"] for cliente in listado.get_json()["clientes"]}

    assert cliente_id not in ids


def test_api_no_elimina_cliente_con_ventas(
    app,
    client,
):
    from tests.test_ventas import _preparar

    ids = _preparar(app, client)

    creacion_cliente = client.post(
        "/api/clientes",
        json={
            "nombre": "Cliente con historial",
            "identificacion_fiscal": "66.666.666-6",
        },
    )

    assert creacion_cliente.status_code == 201

    cliente_id = creacion_cliente.get_json()["id"]

    creacion_venta = client.post(
        "/api/ventas",
        json={
            "numero": "VTA-CLIENTE-001",
            "bodega_id": ids[1],
            "cliente_id": cliente_id,
            "items": [
                {
                    "producto_id": ids[2],
                    "cantidad": 1,
                    "precio_unitario": 100,
                }
            ],
        },
    )

    assert creacion_venta.status_code == 201

    eliminacion = client.delete(f"/api/clientes/{cliente_id}")

    assert eliminacion.status_code == 409

    error = eliminacion.get_json()

    assert error["codigo"] == "cliente_con_historial"
    assert "ventas asociadas" in error["mensaje"]

    listado = client.get("/api/clientes")

    ids_clientes = {cliente["id"] for cliente in listado.get_json()["clientes"]}

    assert cliente_id in ids_clientes


def test_api_clientes_aisla_empresas(client):
    registrar_empresa(client)

    creacion_empresa_a = client.post(
        "/api/clientes",
        json={
            "nombre": "Cliente Empresa A",
            "identificacion_fiscal": "77.777.777-7",
            "email": "cliente@empresa-a.cl",
        },
    )

    assert creacion_empresa_a.status_code == 201

    cliente_empresa_a = creacion_empresa_a.get_json()
    cliente_id = cliente_empresa_a["id"]

    client.post("/autenticacion/salir")

    registro_empresa_b = {
        **REGISTRO,
        "empresa_nombre": "Empresa B",
        "empresa_identificacion_fiscal": "77.111.222-6",
        "identificacion_fiscal": "88.888.888-8",
        "nombre": "Administradora",
        "apellido": "Empresa B",
        "email": "admin@empresa-b.cl",
    }

    registro_b = client.post(
        "/autenticacion/registro",
        data=registro_empresa_b,
    )

    assert registro_b.status_code == 302

    listado_empresa_b = client.get("/api/clientes?incluir_inactivos=true")

    assert listado_empresa_b.status_code == 200

    clientes_empresa_b = listado_empresa_b.get_json()["clientes"]

    assert clientes_empresa_b == []

    edicion_cruzada = client.patch(
        f"/api/clientes/{cliente_id}",
        json={
            "nombre": "Intento Empresa B",
        },
    )

    assert edicion_cruzada.status_code == 403

    desactivacion_cruzada = client.post(f"/api/clientes/{cliente_id}/desactivar")

    assert desactivacion_cruzada.status_code == 403

    eliminacion_cruzada = client.delete(f"/api/clientes/{cliente_id}")

    assert eliminacion_cruzada.status_code == 403

    creacion_empresa_b = client.post(
        "/api/clientes",
        json={
            "nombre": "Cliente Empresa B",
            "identificacion_fiscal": "77.777.777-7",
            "email": "cliente@empresa-b.cl",
        },
    )

    assert creacion_empresa_b.status_code == 201

    cliente_b = creacion_empresa_b.get_json()

    assert cliente_b["nombre"] == "Cliente Empresa B"
    assert cliente_b["identificacion_fiscal"] == "77.777.777-7"
