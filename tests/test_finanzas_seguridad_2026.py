from app.commands import PLANES, errores_integraciones_produccion
from app.models import PlanSaaS, Suscripcion, db
from app.services.suscripciones import ServicioSuscripciones
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        db.session.add(
            PlanSaaS(
                codigo="corporativo",
                nombre="Corporativo",
                precio_mensual=0,
                precio_anual=0,
                funciones={},
                nivel_comercial="corporativo",
            )
        )
        db.session.commit()


def test_catalogo_tiene_cuatro_planes_comerciales_con_prueba():
    planes = {plan["codigo"]: plan for plan in PLANES}
    comerciales = {"avanzado", "ultra", "profesional", "empresa"}
    assert comerciales.issubset(planes)
    assert all(planes[codigo]["dias_prueba"] == 30 for codigo in comerciales)
    assert all(planes[codigo].get("activo", True) for codigo in comerciales)
    assert all(
        not planes[codigo].get("activo", True) for codigo in {"prueba", "basico", "corporativo"}
    )


def test_limites_multisucursal_coinciden_con_capacidades():
    planes = {plan["codigo"]: plan for plan in PLANES}

    limites = {
        "avanzado": (1, 1, False),
        "ultra": (2, 3, True),
        "profesional": (5, 10, True),
        "empresa": (10, 25, True),
    }

    for codigo, (
        sucursales,
        bodegas,
        distribuido,
    ) in limites.items():
        plan = planes[codigo]

        assert plan["limite_sucursales"] == sucursales
        assert plan["limite_bodegas"] == bodegas
        assert plan["funciones"]["multisucursal"] is distribuido
        assert plan["funciones"]["multibodega"] is distribuido
        assert plan["funciones"]["transferencias"] is distribuido


def test_avanzado_inicia_prueba_y_empresarial_es_el_nivel_mayor():
    planes = {plan["codigo"]: plan for plan in PLANES}
    avanzado = planes["avanzado"]
    enterprise = planes["empresa"]
    assert avanzado["dias_prueba"] == 30
    assert avanzado["limite_productos"] == 500
    assert avanzado["limite_usuarios"] == 2
    assert enterprise["nombre"] == "Empresarial"
    assert enterprise["limite_productos"] == 10000
    assert enterprise["limite_usuarios"] == 12


def test_empresarial_es_contrato_y_no_checkout(app, client):
    _preparar(app, client)
    app.test_cli_runner().invoke(args=["seed-planes"])
    respuesta = client.post(
        "/api/suscripciones/solicitudes",
        json={"plan_codigo": "empresa", "ciclo": "anual", "proveedor": "webpay"},
    )
    assert respuesta.status_code == 400
    assert "cotización" in respuesta.get_json()["mensaje"]


def test_planes_internos_no_pueden_seleccionarse_en_registro(app, client):
    for codigo in ("basico", "corporativo"):
        respuesta = client.get(
            f"/autenticacion/registro?plan={codigo}&ciclo=mensual&proveedor=webpay"
        )
        assert respuesta.status_code == 200
        assert f'data-plan-seleccionado="{codigo}"' not in respuesta.get_data(as_text=True)


def test_catalogo_de_compra_excluye_planes_internos(app, client):
    _preparar(app, client)
    respuesta = client.get("/api/suscripciones")
    codigos = {plan["codigo"] for plan in respuesta.get_json()["planes_disponibles"]}
    assert codigos.isdisjoint({"prueba", "basico", "corporativo"})


def test_cancelacion_programada_no_corta_acceso(app, client):
    _preparar(app, client)
    respuesta = client.post(
        "/api/suscripciones/cancelacion-programada", json={"motivo": "Cambio interno"}
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json()["cancelar_al_fin_periodo"] is True
    with client.application.app_context():
        suscripcion = db.session.scalar(db.select(Suscripcion))
        assert suscripcion.esta_vigente() is True
        assert suscripcion.renovacion_automatica is False


def test_reactivar_renovacion(app, client):
    _preparar(app, client)
    with app.app_context():
        suscripcion = db.session.scalar(db.select(Suscripcion))
        suscripcion.metodo_pago_recurrente_estado = "activo"
        suscripcion.referencia_metodo_pago = "token-proveedor-prueba"
        db.session.commit()
    client.post("/api/suscripciones/cancelacion-programada", json={})
    respuesta = client.post("/api/suscripciones/renovacion/reactivar", json={})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["renovacion_automatica"] is True


def test_renovacion_solo_se_activa_tras_confirmacion_tokenizada(app, client):
    _preparar(app, client)
    with app.app_context():
        suscripcion = db.session.scalar(db.select(Suscripcion))
        suscripcion.renovacion_automatica = False
        suscripcion.metodo_pago_recurrente_estado = "pendiente"
        db.session.commit()
        confirmada = ServicioSuscripciones.confirmar_metodo_recurrente(
            empresa_id=suscripcion.empresa_id,
            proveedor="mercadopago",
            referencia="preapproval-tokenizado-123",
        )
        assert confirmada.metodo_pago_recurrente_estado == "activo"
        assert confirmada.renovacion_automatica is True
        assert confirmada.referencia_metodo_pago == "preapproval-tokenizado-123"


def test_verificacion_productiva_exige_2fa_y_password_fuerte():
    errores = errores_integraciones_produccion({})
    assert any("PostgreSQL" in error for error in errores)
    assert any("REQUIRE_PRIVILEGED_2FA" in error for error in errores)
    assert any("PASSWORD_MIN_LENGTH" in error for error in errores)


def test_produccion_permite_jefatura_verificada_sin_2fa(app, client):
    _preparar(app, client)
    app.config["REQUIRE_PRIVILEGED_2FA"] = True
    respuesta = client.get("/api/suscripciones")
    assert respuesta.status_code == 200
