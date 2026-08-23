from decimal import Decimal

import pytest

from app.models import (
    Empresa,
    PresentacionProducto,
    Producto,
    Usuario,
    db,
)
from app.services.productos import (
    ServicioProductos,
)
from app.services.unidades_medida import (
    ErrorUnidadMedida,
    ServicioUnidadesMedida,
)
from tests.test_productos_proveedores import (
    _preparar,
)


def _crear_producto(
    app,
    client,
    *,
    codigo="UM-001",
    unidad_medida="unidad",
):
    usuario_id = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo=codigo,
            nombre="Producto con presentaciones",
            unidad_medida=unidad_medida,
            unidades_por_caja=1,
            costo_referencia=0,
            precio_venta=0,
        )
        db.session.add(producto)
        db.session.commit()

        return usuario_id, producto.id


def test_producto_conserva_unidad_base_existente(
    app,
    client,
):
    usuario_id, producto_id = _crear_producto(
        app,
        client,
        unidad_medida="kilogramo",
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        servicio = ServicioUnidadesMedida(usuario)

        presentaciones = servicio.listar(producto_id)

        assert presentaciones[0] == {
            "id": None,
            "codigo": "base",
            "nombre": "Kilogramo",
            "abreviatura": "kg",
            "factor_base": Decimal("1"),
            "es_base": True,
            "activa": True,
        }


def test_crea_presentacion_y_convierte_a_base(
    app,
    client,
):
    usuario_id, producto_id = _crear_producto(
        app,
        client,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        servicio = ServicioUnidadesMedida(usuario)

        presentacion = servicio.crear(
            producto_id=producto_id,
            codigo="caja-12",
            nombre="Caja de 12",
            abreviatura="cj",
            factor_base=12,
        )

        assert presentacion.factor_base == Decimal("12.000")
        assert servicio.convertir_a_base(
            producto_id=producto_id,
            cantidad=Decimal("2.5"),
            presentacion_id=presentacion.id,
        ) == Decimal("30.000")


def test_presentacion_debe_tener_factor_positivo(
    app,
    client,
):
    usuario_id, producto_id = _crear_producto(
        app,
        client,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        servicio = ServicioUnidadesMedida(usuario)

        with pytest.raises(ErrorUnidadMedida):
            servicio.crear(
                producto_id=producto_id,
                codigo="caja-invalida",
                nombre="Caja inválida",
                abreviatura="cj",
                factor_base=0,
            )


def test_codigo_presentacion_es_unico_por_producto(
    app,
    client,
):
    usuario_id, producto_id = _crear_producto(
        app,
        client,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        servicio = ServicioUnidadesMedida(usuario)

        servicio.crear(
            producto_id=producto_id,
            codigo="display",
            nombre="Display",
            abreviatura="disp",
            factor_base=6,
        )

        with pytest.raises(ErrorUnidadMedida):
            servicio.crear(
                producto_id=producto_id,
                codigo="DISPLAY",
                nombre="Otro display",
                abreviatura="disp",
                factor_base=10,
            )


def test_empresa_no_accede_presentacion_ajena(
    app,
    client,
):
    usuario_id, _ = _crear_producto(
        app,
        client,
    )

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        empresa_ajena = Empresa(
            nombre="Empresa ajena",
            email="unidades-ajena@example.com",
        )
        db.session.add(empresa_ajena)
        db.session.flush()

        producto_ajeno = Producto(
            empresa_id=empresa_ajena.id,
            codigo="AJENO-UM",
            nombre="Producto ajeno",
            unidad_medida="unidad",
            unidades_por_caja=1,
            costo_referencia=0,
            precio_venta=0,
        )
        db.session.add(producto_ajeno)
        db.session.commit()

        servicio = ServicioUnidadesMedida(usuario)

        with pytest.raises(PermissionError):
            servicio.crear(
                producto_id=producto_ajeno.id,
                codigo="caja",
                nombre="Caja",
                abreviatura="cj",
                factor_base=12,
            )

        assert (
            db.session.scalar(
                db.select(db.func.count(PresentacionProducto.id)).where(
                    PresentacionProducto.producto_id == producto_ajeno.id
                )
            )
            == 0
        )


def test_crear_producto_sincroniza_caja_heredada(
    app,
    client,
):
    usuario_id = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )

        producto = ServicioProductos(usuario).crear(
            codigo="CAJA-LEGACY",
            nombre="Producto por caja",
            unidad_medida="unidad",
            unidades_por_caja=12,
        )

        caja = db.session.scalar(
            db.select(PresentacionProducto).where(
                PresentacionProducto.empresa_id == usuario.empresa_id,
                PresentacionProducto.producto_id == producto.id,
                PresentacionProducto.codigo == "CAJA",
            )
        )

        assert caja is not None
        assert caja.nombre == "Caja"
        assert caja.abreviatura == "cj"
        assert caja.factor_base == Decimal("12.000")
        assert caja.activa is True


def test_editar_unidades_por_caja_actualiza_presentacion(
    app,
    client,
):
    usuario_id = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        servicio = ServicioProductos(usuario)

        producto = servicio.crear(
            codigo="CAJA-EDITAR",
            nombre="Producto editable",
            unidad_medida="unidad",
            unidades_por_caja=6,
        )

        servicio.editar(
            producto.id,
            unidades_por_caja=24,
        )

        cajas = list(
            db.session.scalars(
                db.select(PresentacionProducto).where(
                    PresentacionProducto.empresa_id == usuario.empresa_id,
                    PresentacionProducto.producto_id == producto.id,
                    PresentacionProducto.codigo == "CAJA",
                )
            )
        )

        assert len(cajas) == 1
        assert cajas[0].factor_base == Decimal("24.000")
        assert cajas[0].activa is True


def test_unidad_sin_caja_no_crea_presentacion(
    app,
    client,
):
    usuario_id = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )

        producto = ServicioProductos(usuario).crear(
            codigo="SOLO-UNIDAD",
            nombre="Producto unitario",
            unidad_medida="unidad",
            unidades_por_caja=1,
        )

        cantidad = db.session.scalar(
            db.select(db.func.count(PresentacionProducto.id)).where(
                PresentacionProducto.empresa_id == usuario.empresa_id,
                PresentacionProducto.producto_id == producto.id,
            )
        )

        assert cantidad == 0


def test_reducir_unidades_por_caja_desactiva_presentacion(
    app,
    client,
):
    usuario_id = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(
            Usuario,
            usuario_id,
        )
        servicio = ServicioProductos(usuario)

        producto = servicio.crear(
            codigo="CAJA-DESACTIVAR",
            nombre="Caja desactivable",
            unidad_medida="unidad",
            unidades_por_caja=12,
        )

        servicio.editar(
            producto.id,
            unidades_por_caja=1,
        )

        caja = db.session.scalar(
            db.select(PresentacionProducto).where(
                PresentacionProducto.empresa_id == usuario.empresa_id,
                PresentacionProducto.producto_id == producto.id,
                PresentacionProducto.codigo == "CAJA",
            )
        )

        assert caja is not None
        assert caja.activa is False
        assert caja.factor_base == Decimal("12.000")


def test_api_lista_presentaciones_del_producto(
    app,
    client,
):
    _preparar(app, client)

    creacion = client.post(
        "/api/productos",
        json={
            "codigo": "API-UM-LISTA",
            "nombre": "Bebida por caja",
            "unidad_medida": "unidad",
            "unidades_por_caja": 12,
        },
    )

    assert creacion.status_code == 201
    producto_id = creacion.get_json()["id"]

    respuesta = client.get(f"/api/productos/{producto_id}" "/presentaciones")

    assert respuesta.status_code == 200

    datos = respuesta.get_json()

    assert datos["producto_id"] == producto_id
    assert datos["unidad_base"] == {
        "id": None,
        "codigo": "base",
        "nombre": "Unidad",
        "abreviatura": "un",
        "factor_base": "1.000",
        "es_base": True,
        "activa": True,
    }

    assert len(datos["presentaciones"]) == 1

    caja = datos["presentaciones"][0]

    assert caja["codigo"] == "CAJA"
    assert caja["nombre"] == "Caja"
    assert caja["abreviatura"] == "cj"
    assert caja["factor_base"] == "12.000"
    assert caja["es_base"] is False
    assert caja["activa"] is True


def test_api_crea_presentacion_personalizada(
    app,
    client,
):
    _preparar(app, client)

    creacion = client.post(
        "/api/productos",
        json={
            "codigo": "API-UM-CREAR",
            "nombre": "Bebida en display",
            "unidad_medida": "unidad",
        },
    )

    assert creacion.status_code == 201
    producto_id = creacion.get_json()["id"]

    respuesta = client.post(
        f"/api/productos/{producto_id}" "/presentaciones",
        json={
            "codigo": "display-6",
            "nombre": "Display de 6",
            "abreviatura": "disp",
            "factor_base": 6,
        },
    )

    assert respuesta.status_code == 201

    presentacion = respuesta.get_json()

    assert presentacion["id"] is not None
    assert presentacion["codigo"] == "DISPLAY-6"
    assert presentacion["nombre"] == "Display de 6"
    assert presentacion["abreviatura"] == "disp"
    assert presentacion["factor_base"] == "6.000"
    assert presentacion["es_base"] is False
    assert presentacion["activa"] is True

    listado = client.get(f"/api/productos/{producto_id}" "/presentaciones")

    assert listado.status_code == 200
    assert len(listado.get_json()["presentaciones"]) == 1


def test_api_rechaza_factor_presentacion_invalido(
    app,
    client,
):
    _preparar(app, client)

    creacion = client.post(
        "/api/productos",
        json={
            "codigo": "API-UM-ERROR",
            "nombre": "Producto API inválido",
        },
    )

    producto_id = creacion.get_json()["id"]

    respuesta = client.post(
        f"/api/productos/{producto_id}" "/presentaciones",
        json={
            "codigo": "caja-error",
            "nombre": "Caja incorrecta",
            "abreviatura": "cj",
            "factor_base": 0,
        },
    )

    assert respuesta.status_code == 400

    error = respuesta.get_json()

    assert error["codigo"] == "presentacion_invalida"
    assert "mayor que cero" in error["mensaje"]


def test_api_edita_presentacion_personalizada(
    app,
    client,
):
    _preparar(app, client)

    producto = client.post(
        "/api/productos",
        json={
            "codigo": "API-UM-EDITAR",
            "nombre": "Producto editable",
        },
    ).get_json()

    creacion = client.post(
        f"/api/productos/{producto['id']}" "/presentaciones",
        json={
            "codigo": "PACK-6",
            "nombre": "Pack de 6",
            "abreviatura": "pack",
            "factor_base": 6,
        },
    )

    assert creacion.status_code == 201
    presentacion_id = creacion.get_json()["id"]

    respuesta = client.patch(
        f"/api/productos/{producto['id']}" f"/presentaciones/{presentacion_id}",
        json={
            "codigo": "PACK-8",
            "nombre": "Pack de 8",
            "abreviatura": "pack",
            "factor_base": 8,
        },
    )

    assert respuesta.status_code == 200

    datos = respuesta.get_json()

    assert datos["id"] == presentacion_id
    assert datos["codigo"] == "PACK-8"
    assert datos["nombre"] == "Pack de 8"
    assert datos["factor_base"] == "8.000"
    assert datos["activa"] is True


def test_api_desactiva_presentacion_personalizada(
    app,
    client,
):
    _preparar(app, client)

    producto = client.post(
        "/api/productos",
        json={
            "codigo": "API-UM-DESACTIVAR",
            "nombre": "Producto desactivable",
        },
    ).get_json()

    presentacion = client.post(
        f"/api/productos/{producto['id']}" "/presentaciones",
        json={
            "codigo": "DISPLAY-4",
            "nombre": "Display de 4",
            "abreviatura": "disp",
            "factor_base": 4,
        },
    ).get_json()

    respuesta = client.post(
        f"/api/productos/{producto['id']}" f"/presentaciones/" f"{presentacion['id']}/desactivar"
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["activa"] is False

    listado = client.get(f"/api/productos/{producto['id']}" "/presentaciones").get_json()

    assert listado["presentaciones"] == []


def test_api_impide_editar_caja_administrada(
    app,
    client,
):
    _preparar(app, client)

    producto = client.post(
        "/api/productos",
        json={
            "codigo": "API-UM-CAJA",
            "nombre": "Caja administrada",
            "unidades_por_caja": 12,
        },
    ).get_json()

    listado = client.get(f"/api/productos/{producto['id']}" "/presentaciones").get_json()

    caja = listado["presentaciones"][0]

    respuesta = client.patch(
        f"/api/productos/{producto['id']}" f"/presentaciones/{caja['id']}",
        json={
            "factor_base": 24,
        },
    )

    assert respuesta.status_code == 400

    error = respuesta.get_json()

    assert error["codigo"] == "presentacion_invalida"
    assert "unidades_por_caja" in error["mensaje"]
