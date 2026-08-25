import pytest

from app.models import (
    ConfiguracionEmpresa,
    Empresa,
    Inventario,
    Movimiento,
    Producto,
    Proveedor,
    Usuario,
    db,
)
from app.services.productos import ErrorProducto, LimiteProductosAlcanzado, ServicioProductos
from app.services.proveedores import ErrorProveedor, ServicioProveedores
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        usuario.empresa.suscripcion_actual.plan.funciones = {
            **usuario.empresa.suscripcion_actual.plan.funciones,
            "proveedores.avanzados": True,
        }
        db.session.commit()
        return usuario.id


def _configurar_rubro(app, rubro):
    with app.app_context():
        configuracion = db.session.scalar(db.select(ConfiguracionEmpresa))
        configuracion.opciones = {
            "rubro": rubro,
            "capacidades": {},
        }
        db.session.commit()


def test_crear_producto_y_proveedor_auditable(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        proveedor = ServicioProveedores(usuario).crear(
            nombre="Proveedor Uno", identificacion_fiscal="76.111.111-6", dias_entrega=5
        )
        producto = ServicioProductos(usuario).crear(
            codigo="abc-1",
            nombre="Martillo",
            proveedor_principal_id=proveedor.id,
            costo_referencia=1000,
            precio_venta=1800,
            stock_minimo=2,
            stock_maximo=20,
        )
        assert producto.codigo == "ABC-1"
        assert producto.proveedor_principal_id == proveedor.id


def test_codigo_producto_unico_por_empresa(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        servicio = ServicioProductos(db.session.get(Usuario, usuario_id))
        servicio.crear(codigo="P-1", nombre="Uno")
        with pytest.raises(ErrorProducto):
            servicio.crear(codigo="P-1", nombre="Duplicado")


def test_mismo_codigo_permitido_en_empresas_distintas(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        ServicioProductos(usuario).crear(codigo="COMUN", nombre="Empresa uno")
        otra = Empresa(nombre="Otra", email="otra-producto@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        db.session.add(
            Producto(
                empresa_id=otra.id,
                codigo="COMUN",
                nombre="Empresa dos",
                costo_referencia=0,
                precio_venta=0,
            )
        )
        db.session.commit()
        assert (
            db.session.scalar(
                db.select(db.func.count(Producto.id)).where(Producto.codigo == "COMUN")
            )
            == 2
        )


def test_proveedor_ajeno_no_se_puede_asignar(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        otra = Empresa(nombre="Otra", email="otra-proveedor@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        ajeno = Proveedor(empresa_id=otra.id, nombre="Ajeno")
        db.session.add(ajeno)
        db.session.commit()
        ajeno_id = ajeno.id
        with pytest.raises(PermissionError):
            ServicioProductos(usuario).crear(
                codigo="P-2", nombre="Producto", proveedor_principal_id=ajeno_id
            )


def test_limite_productos_no_cuenta_eliminados(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        usuario.empresa.suscripcion_actual.plan.limite_productos = 1
        db.session.commit()
        servicio = ServicioProductos(usuario)
        primero = servicio.crear(codigo="P-1", nombre="Primero")
        with pytest.raises(LimiteProductosAlcanzado):
            servicio.crear(codigo="P-2", nombre="Segundo")
        servicio.eliminar_logicamente(primero.id)
        segundo = servicio.crear(codigo="P-2", nombre="Segundo")
        assert segundo.id is not None


def test_producto_con_historial_solo_se_desactiva(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        producto = ServicioProductos(usuario).crear(codigo="HIST", nombre="Histórico")
        # Un saldo materializado basta para impedir eliminación lógica.
        from app.models import Bodega

        bodega = db.session.scalar(db.select(Bodega))
        db.session.add(
            Inventario(
                empresa_id=usuario.empresa_id,
                bodega_id=bodega.id,
                producto_id=producto.id,
                cantidad=1,
                cantidad_reservada=0,
                costo_promedio=10,
            )
        )
        db.session.commit()
        with pytest.raises(ErrorProducto):
            ServicioProductos(usuario).eliminar_logicamente(producto.id)
        ServicioProductos(usuario).desactivar(producto.id)
        assert not db.session.get(Producto, producto.id).activo


def test_proveedor_con_producto_no_se_elimina(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        proveedor = ServicioProveedores(usuario).crear(nombre="Relacionado")
        ServicioProductos(usuario).crear(
            codigo="REL", nombre="Relacionado", proveedor_principal_id=proveedor.id
        )
        with pytest.raises(ErrorProveedor):
            ServicioProveedores(usuario).eliminar_logicamente(proveedor.id)


def test_api_solo_lista_productos_de_empresa_actual(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        ServicioProductos(usuario).crear(codigo="MIO", nombre="Mío")
        otra = Empresa(nombre="Otra", email="otra-api@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        db.session.add(
            Producto(
                empresa_id=otra.id,
                codigo="SECRETO",
                nombre="Secreto",
                costo_referencia=0,
                precio_venta=0,
            )
        )
        db.session.commit()
    respuesta = client.get("/api/productos")
    codigos = [p["codigo"] for p in respuesta.get_json()["productos"]]
    assert codigos == ["MIO"]


def test_api_crea_producto_sin_aceptar_empresa_id(app, client):
    _preparar(app, client)
    respuesta = client.post(
        "/api/productos",
        json={
            "empresa_id": 999999,
            "codigo": "API-1",
            "nombre": "Desde API",
            "precio_venta": 100,
        },
    )
    assert respuesta.status_code == 201
    with app.app_context():
        producto = db.session.scalar(db.select(Producto).where(Producto.codigo == "API-1"))
        usuario = db.session.scalar(db.select(Usuario))
        assert producto.empresa_id == usuario.empresa_id


def test_edicion_parcial_conserva_campos(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        producto = ServicioProductos(usuario).crear(
            codigo="PARCIAL", nombre="Original", precio_venta=100, costo_referencia=50
        )
        producto_id = producto.id
    respuesta = client.patch(f"/api/productos/{producto_id}", json={"precio_venta": 150})
    assert respuesta.status_code == 200
    with app.app_context():
        producto = db.session.get(Producto, producto_id)
        assert producto.codigo == "PARCIAL"
        assert producto.nombre == "Original"
        assert producto.precio_venta == 150


def test_producto_admite_campos_personalizados_y_los_aisla(app, client):
    _preparar(app, client)
    respuesta = client.post(
        "/api/productos",
        json={
            "codigo": "CUSTOM-1",
            "nombre": "Producto configurable",
            "campos_personalizados": {"Color": "Azul", "Temporada": "Invierno"},
        },
    )
    assert respuesta.status_code == 201
    assert respuesta.get_json()["campos_personalizados"] == {
        "Color": "Azul",
        "Temporada": "Invierno",
    }


def test_campos_personalizados_rechazan_objetos_anidados(app, client):
    _preparar(app, client)
    respuesta = client.post(
        "/api/productos",
        json={
            "codigo": "CUSTOM-2",
            "nombre": "Inválido",
            "campos_personalizados": {"interno": {"secreto": True}},
        },
    )
    assert respuesta.status_code == 400


def test_etiqueta_producto_entrega_qr_autocontenido(app, client):
    _preparar(app, client)
    creado = client.post(
        "/api/productos",
        json={"codigo": "QR-1", "codigo_barras": "7801234567890", "nombre": "Etiquetado"},
    ).get_json()
    respuestas = [client.get(f"/api/productos/{creado['id']}/etiqueta") for _ in range(12)]

    assert all(respuesta.status_code == 200 for respuesta in respuestas)

    for respuesta in respuestas:
        datos = respuesta.get_json()

        assert datos["producto"]["codigo_barras"] == "7801234567890"
        assert datos["producto"]["qr"].startswith("data:image/svg+xml;base64,")


def test_id_ajeno_en_api_responde_403(app, client):
    _preparar(app, client)
    with app.app_context():
        otra = Empresa(nombre="Ajena", email="ajena-idor@nexustock.cl")
        db.session.add(otra)
        db.session.flush()
        producto = Producto(
            empresa_id=otra.id, codigo="IDOR", nombre="Ajeno", costo_referencia=0, precio_venta=0
        )
        db.session.add(producto)
        db.session.commit()
        producto_id = producto.id
    respuesta = client.patch(f"/api/productos/{producto_id}", json={"nombre": "Hack"})
    assert respuesta.status_code == 403
    with app.app_context():
        assert db.session.get(Producto, producto_id).nombre == "Ajeno"


def test_api_producto_expone_campos_editables(app, client):
    _preparar(app, client)
    _configurar_rubro(app, "minimarket")

    respuesta_creacion = client.post(
        "/api/productos",
        json={
            "codigo": "COMPLETO-1",
            "codigo_barras": "7801234567890",
            "nombre": "Producto completo",
            "descripcion": "Descripción de prueba",
            "categoria": "Categoría",
            "subcategoria": "Subcategoría",
            "marca": "Marca",
            "unidad_medida": "unidad",
            "unidades_por_caja": 12,
            "costo_referencia": 1000,
            "precio_venta": 1500,
            "incluye_iva": True,
            "tasa_impuesto": "0.19",
            "stock_minimo": 2,
            "punto_reorden": 4,
            "stock_maximo": 20,
            "requiere_serial": False,
            "controla_lotes": True,
            "controla_vencimiento": True,
        },
    )

    assert respuesta_creacion.status_code == 201

    producto = respuesta_creacion.get_json()

    campos_esperados = {
        "id",
        "codigo",
        "codigo_barras",
        "nombre",
        "descripcion",
        "categoria",
        "subcategoria",
        "marca",
        "unidad_medida",
        "unidades_por_caja",
        "costo_referencia",
        "precio_venta",
        "incluye_iva",
        "tasa_impuesto",
        "stock_minimo",
        "punto_reorden",
        "stock_maximo",
        "requiere_serial",
        "controla_lotes",
        "controla_vencimiento",
        "activo",
        "proveedor_principal_id",
    }

    assert campos_esperados.issubset(producto)


def test_api_desactiva_producto_sin_eliminarlo(app, client):
    _preparar(app, client)

    respuesta_creacion = client.post(
        "/api/productos",
        json={
            "codigo": "DESACTIVAR-1",
            "nombre": "Producto para desactivar",
            "precio_venta": 1000,
        },
    )

    assert respuesta_creacion.status_code == 201

    producto_id = respuesta_creacion.get_json()["id"]

    respuesta_desactivacion = client.post(f"/api/productos/{producto_id}/desactivar")

    assert respuesta_desactivacion.status_code == 200

    producto_desactivado = respuesta_desactivacion.get_json()

    assert producto_desactivado["id"] == producto_id
    assert producto_desactivado["activo"] is False

    respuesta_listado = client.get("/api/productos")

    assert respuesta_listado.status_code == 200

    identificadores_visibles = {
        producto["id"] for producto in respuesta_listado.get_json()["productos"]
    }

    assert producto_id not in identificadores_visibles

    with app.app_context():
        producto_guardado = db.session.get(Producto, producto_id)

        assert producto_guardado is not None
        assert producto_guardado.activo is False
        assert producto_guardado.eliminado is False


def test_api_lista_inactivos_y_reactiva_producto(app, client):
    _preparar(app, client)

    respuesta_creacion = client.post(
        "/api/productos",
        json={
            "codigo": "REACTIVAR-1",
            "nombre": "Producto para reactivar",
            "precio_venta": 1500,
        },
    )

    assert respuesta_creacion.status_code == 201

    producto_id = respuesta_creacion.get_json()["id"]

    respuesta_desactivacion = client.post(f"/api/productos/{producto_id}/desactivar")

    assert respuesta_desactivacion.status_code == 200

    listado_activo = client.get("/api/productos")
    ids_activos = {producto["id"] for producto in listado_activo.get_json()["productos"]}

    assert producto_id not in ids_activos

    listado_completo = client.get("/api/productos?incluir_inactivos=true")

    assert listado_completo.status_code == 200

    productos_completos = listado_completo.get_json()["productos"]
    producto_inactivo = next(
        producto for producto in productos_completos if producto["id"] == producto_id
    )

    assert producto_inactivo["activo"] is False

    respuesta_reactivacion = client.post(f"/api/productos/{producto_id}/reactivar")

    assert respuesta_reactivacion.status_code == 200
    assert respuesta_reactivacion.get_json()["activo"] is True

    listado_final = client.get("/api/productos")
    ids_finales = {producto["id"] for producto in listado_final.get_json()["productos"]}

    assert producto_id in ids_finales


def test_api_proveedor_expone_campos_editables(app, client):
    _preparar(app, client)

    respuesta_creacion = client.post(
        "/api/proveedores",
        json={
            "nombre": "Distribuidora Completa",
            "identificacion_fiscal": "76.555.444-6",
            "email": "ventas@distribuidora.cl",
            "telefono": "+56912345678",
            "direccion": "Avenida Central 123",
            "ciudad": "Santiago",
            "pais": "CL",
            "sitio_web": "https://distribuidora.cl",
            "condiciones_pago": "30 días",
            "dias_entrega": 5,
            "compra_minima": 50000,
            "observaciones": "Proveedor prioritario",
        },
    )

    assert respuesta_creacion.status_code == 201

    proveedor = respuesta_creacion.get_json()

    campos_esperados = {
        "id",
        "nombre",
        "identificacion_fiscal",
        "email",
        "telefono",
        "direccion",
        "ciudad",
        "pais",
        "sitio_web",
        "condiciones_pago",
        "dias_entrega",
        "compra_minima",
        "observaciones",
        "activo",
    }

    assert campos_esperados.issubset(proveedor)

    assert proveedor["nombre"] == "Distribuidora Completa"
    assert proveedor["pais"] == "CL"
    assert proveedor["condiciones_pago"] == "30 días"


def test_api_busca_desactiva_y_reactiva_proveedor(
    app,
    client,
):
    _preparar(app, client)

    respuesta_principal = client.post(
        "/api/proveedores",
        json={
            "nombre": "Distribuidora Austral",
            "identificacion_fiscal": "76.101.101-4",
            "ciudad": "Puerto Montt",
        },
    )

    respuesta_secundaria = client.post(
        "/api/proveedores",
        json={
            "nombre": "Comercial Central",
            "identificacion_fiscal": "76.202.202-8",
            "ciudad": "Santiago",
        },
    )

    assert respuesta_principal.status_code == 201
    assert respuesta_secundaria.status_code == 201

    proveedor_id = respuesta_principal.get_json()["id"]

    respuesta_busqueda = client.get("/api/proveedores?buscar=Austral")

    assert respuesta_busqueda.status_code == 200

    nombres_encontrados = {
        proveedor["nombre"] for proveedor in respuesta_busqueda.get_json()["proveedores"]
    }

    assert nombres_encontrados == {"Distribuidora Austral"}

    respuesta_desactivacion = client.post(f"/api/proveedores/{proveedor_id}/desactivar")

    assert respuesta_desactivacion.status_code == 200
    assert respuesta_desactivacion.get_json()["activo"] is False

    listado_activo = client.get("/api/proveedores")
    ids_activos = {proveedor["id"] for proveedor in listado_activo.get_json()["proveedores"]}

    assert proveedor_id not in ids_activos

    listado_completo = client.get("/api/proveedores?incluir_inactivos=true")

    ids_completos = {proveedor["id"] for proveedor in listado_completo.get_json()["proveedores"]}

    assert proveedor_id in ids_completos

    respuesta_reactivacion = client.post(f"/api/proveedores/{proveedor_id}/reactivar")

    assert respuesta_reactivacion.status_code == 200
    assert respuesta_reactivacion.get_json()["activo"] is True


def test_api_general_rechaza_control_de_lotes(
    app,
    client,
):
    _preparar(app, client)

    respuesta = client.post(
        "/api/productos",
        json={
            "codigo": "GENERAL-LOTE",
            "nombre": "Producto manipulado",
            "precio_venta": 1000,
            "controla_lotes": True,
        },
    )

    assert respuesta.status_code == 400
    assert respuesta.get_json()["codigo"] == "producto_invalido"

    with app.app_context():
        producto = db.session.scalar(db.select(Producto).where(Producto.codigo == "GENERAL-LOTE"))

        assert producto is None


def test_api_general_rechaza_control_vencimiento(
    app,
    client,
):
    _preparar(app, client)

    respuesta = client.post(
        "/api/productos",
        json={
            "codigo": "GENERAL-VENCE",
            "nombre": "Producto manipulado",
            "precio_venta": 1000,
            "controla_vencimiento": True,
        },
    )

    assert respuesta.status_code == 400


def test_api_minimarket_permite_trazabilidad(
    app,
    client,
):
    _preparar(app, client)
    _configurar_rubro(app, "minimarket")

    respuesta = client.post(
        "/api/productos",
        json={
            "codigo": "MINI-LOTE",
            "nombre": "Producto perecible",
            "precio_venta": 1000,
            "controla_lotes": True,
            "controla_vencimiento": True,
        },
    )

    assert respuesta.status_code == 201

    producto = respuesta.get_json()

    assert producto["controla_lotes"] is True
    assert producto["controla_vencimiento"] is True


def test_api_general_no_habilita_lotes_al_editar(
    app,
    client,
):
    _preparar(app, client)

    creacion = client.post(
        "/api/productos",
        json={
            "codigo": "GENERAL-EDITAR",
            "nombre": "Producto general",
            "precio_venta": 1000,
        },
    )

    assert creacion.status_code == 201

    producto_id = creacion.get_json()["id"]

    respuesta = client.patch(
        f"/api/productos/{producto_id}",
        json={
            "controla_lotes": True,
        },
    )

    assert respuesta.status_code == 400

    with app.app_context():
        producto = db.session.get(
            Producto,
            producto_id,
        )

        assert producto.controla_lotes is False
