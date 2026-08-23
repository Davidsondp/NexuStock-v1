from decimal import Decimal

from app.models import (
    PlanSaaS,
    SolicitudCambioPlan,
    Suscripcion,
    Usuario,
    db,
)
from app.services.suscripciones import ServicioSuscripciones
from tests.test_autenticacion import REGISTRO


def crear_plan_comercial(app):
    with app.app_context():
        plan = PlanSaaS(
            codigo="profesional",
            nombre="Profesional",
            descripcion=("Control avanzado para empresas " "en crecimiento."),
            precio_mensual=Decimal("29990.00"),
            precio_anual=Decimal("299900.00"),
            moneda="CLP",
            dias_prueba=30,
            limite_productos=5000,
            limite_usuarios=10,
            limite_movimientos_mes=50000,
            limite_sucursales=1,
            limite_bodegas=1,
            almacenamiento_mb=10000,
            funciones={
                "productos": True,
                "inventario": True,
                "ventas": True,
                "compras": True,
                "reportes": True,
                "analitica": True,
            },
            activo=True,
            orden=20,
        )

        db.session.add(plan)
        db.session.commit()

        return plan.id


def test_registro_muestra_plan_comercial_seleccionado(
    app,
    client,
):
    crear_plan_comercial(app)

    respuesta = client.get("/autenticacion/registro?plan=profesional&ciclo=anual&proveedor=webpay")

    assert respuesta.status_code == 200
    assert b"data-plan-seleccionado=" b'"profesional"' in respuesta.data
    assert b'data-ciclo-seleccionado="anual"' in respuesta.data
    assert b'id="resumen-plan-seleccionado"' in respuesta.data
    assert b'id="resumen-ciclo-seleccionado"' in respuesta.data
    assert b"Profesional" in respuesta.data
    assert b"Anual" in respuesta.data
    for contrato in (
        b'class="registro-progreso"',
        b'data-paso="1"',
        b'data-paso="2"',
        b'data-paso="3"',
        b'data-paso="4"',
        b'id="registro-siguiente"',
        b'id="registro-anterior"',
        b'id="registro-enviar"',
    ):
        assert contrato in respuesta.data


def test_registro_crea_solicitud_comercial_atomica(
    app,
    client,
):
    plan_id = crear_plan_comercial(app)

    seleccion = client.get("/autenticacion/registro?plan=profesional&ciclo=anual&proveedor=webpay")

    assert seleccion.status_code == 200

    respuesta = client.post(
        "/autenticacion/registro",
        data=REGISTRO,
    )

    assert respuesta.status_code == 302

    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario).where(Usuario.email == REGISTRO["email"]))

        assert usuario is not None

        suscripcion = db.session.scalar(
            db.select(Suscripcion).where(Suscripcion.empresa_id == usuario.empresa_id)
        )

        solicitud = db.session.scalar(
            db.select(SolicitudCambioPlan).where(
                SolicitudCambioPlan.empresa_id == usuario.empresa_id
            )
        )

        assert suscripcion is not None
        assert suscripcion.estado == "prueba"
        assert suscripcion.plan_id == plan_id
        assert suscripcion.fecha_fin is None
        assert suscripcion.periodo_actual_inicio is None
        assert suscripcion.esta_vigente() is False
        assert suscripcion.metodo_pago_recurrente_estado == "pendiente"

        ServicioSuscripciones.confirmar_metodo_recurrente(
            empresa_id=usuario.empresa_id,
            proveedor="webpay",
            referencia="tbk-user-confirmado",
        )
        db.session.refresh(suscripcion)
        assert (suscripcion.fecha_fin - suscripcion.fecha_inicio).days == 30
        assert suscripcion.esta_vigente() is True

        assert solicitud is not None
        assert solicitud.plan_solicitado_id == plan_id
        assert solicitud.solicitada_por_id == usuario.id
        assert solicitud.estado == "pendiente"
        assert solicitud.ciclo == "anual"
        assert solicitud.monto_esperado == Decimal("299900.00")
        assert solicitud.moneda == "CLP"
        assert solicitud.proveedor_preferido == "webpay"


def test_registro_no_confia_en_plan_enviado_por_formulario(
    app,
    client,
):
    crear_plan_comercial(app)

    datos = dict(REGISTRO)
    datos.update(
        {
            "plan": "profesional",
            "ciclo": "anual",
        }
    )

    respuesta = client.post(
        "/autenticacion/registro",
        data=datos,
    )

    assert respuesta.status_code == 302

    with app.app_context():
        solicitud = db.session.scalar(db.select(SolicitudCambioPlan))

        assert solicitud is None


def test_seleccion_invalida_no_se_conserva(
    app,
    client,
):
    crear_plan_comercial(app)

    respuesta = client.get("/autenticacion/registro" "?plan=plan-manipulado" "&ciclo=semanal")

    assert respuesta.status_code == 200
    assert b"data-plan-seleccionado=" not in respuesta.data

    with client.session_transaction() as sesion:
        assert "registro_plan_seleccionado" not in sesion
        assert "registro_ciclo_seleccionado" not in sesion


def test_seleccion_sobrevive_error_de_validacion(
    app,
    client,
):
    crear_plan_comercial(app)

    client.get("/autenticacion/registro?plan=profesional&ciclo=mensual&proveedor=webpay")

    datos = dict(REGISTRO)
    datos["email"] = "correo-invalido"

    respuesta = client.post(
        "/autenticacion/registro",
        data=datos,
    )

    assert respuesta.status_code == 200
    assert b"data-plan-seleccionado=" b'"profesional"' in respuesta.data
    assert b'data-ciclo-seleccionado="mensual"' in respuesta.data
    assert b"Profesional" in respuesta.data
    assert b"Mensual" in respuesta.data
