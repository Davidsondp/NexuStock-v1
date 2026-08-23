import pytest

from app.models import Auditoria, Empresa, Usuario, db
from app.services.configuracion import ErrorConfiguracion, ServicioConfiguracion
from app.models import AlertaInventario, Bodega, Inventario, Producto
from app.services.alertas import ServicioAlertas
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        return db.session.scalar(db.select(Usuario.id))


def test_obtener_separa_empresa_preferencias_y_suscripcion(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        datos = ServicioConfiguracion(db.session.get(Usuario, usuario_id)).resumen()
        assert set(datos) == {"empresa", "preferencias", "suscripcion"}
        assert datos["empresa"]["moneda"] == "CLP"
        assert datos["suscripcion"]["codigo_plan"] == "prueba"
        assert "limites" not in datos["empresa"]


def test_edita_datos_locales_validos(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        empresa = ServicioConfiguracion(db.session.get(Usuario, usuario_id)).editar_empresa(
            nombre="Nexu Comercial",
            telefono="+56 9 1234 5678",
            ciudad="Santiago",
            pais="CL",
            moneda="USD",
            idioma="es",
            zona_horaria="America/Santiago",
        )
        assert empresa.nombre == "Nexu Comercial" and empresa.moneda == "USD"


def test_rechaza_zona_moneda_idioma_y_correo_invalidos(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        servicio = ServicioConfiguracion(db.session.get(Usuario, usuario_id))
        for datos in (
            {"zona_horaria": "Chile/Falsa"},
            {"moneda": "BTC"},
            {"idioma": "xx"},
            {"email": "correo-invalido"},
        ):
            with pytest.raises(ErrorConfiguracion):
                servicio.editar_empresa(**datos)


def test_no_permite_modificar_plan_estado_ni_limites(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        plan_id = usuario.empresa.suscripcion_actual.plan_id
        servicio = ServicioConfiguracion(usuario)
        for campo in ("plan_id", "estado", "limite_usuarios", "precio_mensual"):
            with pytest.raises(ErrorConfiguracion):
                servicio.editar_empresa(**{campo: 999})
        assert usuario.empresa.suscripcion_actual.plan_id == plan_id
        assert usuario.empresa.estado == "activa"


def test_preferencias_validan_color_logo_alertas_y_dias(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        _, configuracion = ServicioConfiguracion(
            db.session.get(Usuario, usuario_id)
        ).editar_preferencias(
            nombre_comercial="Mi negocio",
            logo_url="https://cdn.ejemplo.cl/logo.png",
            color_principal="#A1B2C3",
            alerta_stock_bajo=False,
            alerta_sobrestock=True,
            dias_sin_movimiento=45,
        )
        assert configuracion.color_principal == "#A1B2C3"
        assert configuracion.dias_sin_movimiento == 45 and not configuracion.alerta_stock_bajo
        servicio = ServicioConfiguracion(db.session.get(Usuario, usuario_id))
        for datos in (
            {"color_principal": "rojo"},
            {"logo_url": "http://inseguro.cl/logo.png"},
            {"dias_sin_movimiento": 0},
            {"alerta_stock_bajo": "sí"},
        ):
            with pytest.raises(ErrorConfiguracion):
                servicio.editar_preferencias(**datos)


def test_opciones_solo_aceptan_catalogo_y_tipos_definidos(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        servicio = ServicioConfiguracion(db.session.get(Usuario, usuario_id))
        _, configuracion = servicio.editar_preferencias(
            opciones={
                "mostrar_costos_dashboard": True,
                "mostrar_stock_cero": False,
                "decimales_cantidad": 3,
                "formato_fecha": "DD-MM-AAAA",
            }
        )
        assert configuracion.opciones["decimales_cantidad"] == 3
        with pytest.raises(ErrorConfiguracion):
            servicio.editar_preferencias(opciones={"plan_oculto": True})
        with pytest.raises(ErrorConfiguracion):
            servicio.editar_preferencias(opciones={"decimales_cantidad": 9})


def test_cambio_de_correo_e_identificacion_respeta_unicidad(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        otra = Empresa(
            nombre="Otra", email="otra-config@nexustock.cl", identificacion_fiscal="76.000.001-9"
        )
        db.session.add(otra)
        db.session.commit()
        servicio = ServicioConfiguracion(db.session.get(Usuario, usuario_id))
        with pytest.raises(ErrorConfiguracion):
            servicio.editar_empresa(email="otra-config@nexustock.cl")
        with pytest.raises(ErrorConfiguracion):
            servicio.editar_empresa(identificacion_fiscal="76.000.001-9")


def test_configuracion_genera_auditoria_con_antes_y_despues(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        ServicioConfiguracion(db.session.get(Usuario, usuario_id)).editar_preferencias(
            color_principal="#112233"
        )
        auditoria = db.session.scalar(
            db.select(Auditoria).where(Auditoria.accion == "configuracion.editada")
        )
        assert auditoria.datos_anteriores["color_principal"] == "#2563EB"
        assert auditoria.datos_nuevos["color_principal"] == "#112233"


def test_api_rechaza_intento_de_cambiar_plan(app, client):
    _preparar(app, client)
    respuesta = client.patch(
        "/api/configuracion/empresa",
        json={"nombre": "Permitido", "plan_id": 999, "limite_usuarios": 9999},
    )
    assert respuesta.status_code == 400
    assert "no editables" in respuesta.get_json()["mensaje"]


def test_api_configuracion_completamente_en_espanol(app, client):
    _preparar(app, client)
    respuesta = client.patch(
        "/api/configuracion/preferencias",
        json={"nombre_comercial": "Negocio actualizado", "dias_sin_movimiento": 60},
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json()["preferencias"]["nombre_comercial"] == "Negocio actualizado"


def test_panel_configuracion_existe_para_administrador(app, client):
    _preparar(app, client)
    respuesta = client.get("/panel/administracion/configuracion")
    assert respuesta.status_code == 200
    assert "Configuración empresarial" in respuesta.get_data(as_text=True)


def test_preferencia_desactiva_y_resuelve_alerta_de_stock_bajo(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        bodega = db.session.scalar(db.select(Bodega).where(Bodega.empresa_id == usuario.empresa_id))
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="CFG-A",
            nombre="Configurable",
            costo_referencia=1,
            precio_venta=2,
            stock_minimo=5,
            punto_reorden=0,
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
                costo_promedio=1,
            )
        )
        db.session.commit()
        servicio_alertas = ServicioAlertas(usuario)
        servicio_alertas.generar()
        alerta = db.session.scalar(
            db.select(AlertaInventario).where(AlertaInventario.tipo == "stock_bajo")
        )
        assert alerta.estado == "activa"
        ServicioConfiguracion(usuario).editar_preferencias(alerta_stock_bajo=False)
        servicio_alertas.generar()
        db.session.refresh(alerta)
        assert alerta.estado == "resuelta"
