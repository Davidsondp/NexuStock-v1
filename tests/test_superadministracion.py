import pytest

from app.models import (
    Auditoria,
    Empresa,
    Inventario,
    PlanSaaS,
    SolicitudContratoEmpresarial,
    Suscripcion,
    Usuario,
    db,
)
from app.services.inventario import ServicioInventario
from app.services.superadministracion import ErrorSuperAdministracion, ServicioSuperAdministracion
from tests.test_autenticacion import REGISTRO


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    client.post("/autenticacion/salir")
    with app.app_context():
        empresa = db.session.scalar(db.select(Empresa))
        superadmin = Usuario(
            empresa_id=None,
            nombre="Super",
            email="super@nexustock.cl",
            rol="super_admin",
            activo=True,
        )
        superadmin.set_password("ClaveSuper123")
        db.session.add(superadmin)
        db.session.commit()
        return superadmin.id, empresa.id


def _login(client):
    return client.post(
        "/autenticacion/ingresar", data={"email": "super@nexustock.cl", "password": "ClaveSuper123"}
    )


def test_resumen_global_no_expone_inventario(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        datos = ServicioSuperAdministracion(db.session.get(Usuario, ids[0])).resumen()
        assert datos["empresas"] == 1 and datos["usuarios_empresariales"] == 1
        assert "stock" not in datos and "inventario" not in datos


def test_analitica_global_entrega_series_sin_inventario(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        datos = ServicioSuperAdministracion(db.session.get(Usuario, ids[0])).analitica(meses=6)
        assert len(datos["serie"]) == 6
        assert datos["moneda"] == "CLP"
        assert datos["crecimiento_ingresos_pct"] is None
        assert "stock" not in datos and "inventario" not in datos
        assert sum(punto["nuevas_empresas"] for punto in datos["serie"]) == 1


def test_analitica_rechaza_periodo_no_soportado(app, client):
    ids = _preparar(app, client)
    with app.app_context(), pytest.raises(ErrorSuperAdministracion):
        ServicioSuperAdministracion(db.session.get(Usuario, ids[0])).analitica(meses=7)


def test_suspender_empresa_revoca_sesiones_y_reactivar(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioSuperAdministracion(db.session.get(Usuario, ids[0]))
        usuario = db.session.scalar(db.select(Usuario).where(Usuario.empresa_id == ids[1]))
        version = usuario.version_sesion
        empresa = servicio.cambiar_estado_empresa(
            ids[1], estado="suspendida", motivo="Incumplimiento"
        )
        assert empresa.estado == "suspendida" and usuario.version_sesion == version + 1
        servicio.cambiar_estado_empresa(ids[1], estado="activa", motivo=None)
        assert empresa.estado == "activa" and empresa.motivo_suspension is None


def test_suspension_exige_motivo(app, client):
    ids = _preparar(app, client)
    with app.app_context(), pytest.raises(ErrorSuperAdministracion):
        ServicioSuperAdministracion(db.session.get(Usuario, ids[0])).cambiar_estado_empresa(
            ids[1], estado="suspendida", motivo=""
        )


def test_editar_plan_valida_precio_limites_y_funciones(app, client):
    ids = _preparar(app, client)
    app.test_cli_runner().invoke(args=["seed-planes"])
    with app.app_context():
        servicio = ServicioSuperAdministracion(db.session.get(Usuario, ids[0]))
        plan = db.session.scalar(db.select(PlanSaaS).where(PlanSaaS.codigo == "avanzado"))
        servicio.editar_plan(
            plan.id,
            precio_mensual=10990,
            limite_usuarios=7,
            funciones={"productos": True, "analitica": False},
        )
        assert plan.precio_mensual == 10990 and plan.limite_usuarios == 7
        with pytest.raises(ErrorSuperAdministracion):
            servicio.editar_plan(plan.id, dias_prueba=29)
        with pytest.raises(ErrorSuperAdministracion):
            servicio.editar_plan(plan.id, precio_mensual=-1)
        with pytest.raises(ErrorSuperAdministracion):
            servicio.editar_plan(plan.id, funciones={"api": "sí"})


def test_superadmin_no_permite_productos_ilimitados(
    app,
    client,
):
    _preparar(app, client)
    app.test_cli_runner().invoke(args=["seed-planes"])
    _login(client)

    with app.app_context():
        plan_id = db.session.scalar(db.select(PlanSaaS.id).where(PlanSaaS.codigo == "avanzado"))

    respuesta = client.patch(
        f"/api/superadmin/planes/{plan_id}",
        json={
            "limite_productos": None,
        },
    )

    assert respuesta.status_code == 400
    assert "límite de artículos únicos es obligatorio" in respuesta.get_json()["mensaje"]


def test_superadmin_no_permite_limite_productos_cero(
    app,
    client,
):
    _preparar(app, client)
    app.test_cli_runner().invoke(args=["seed-planes"])
    _login(client)

    with app.app_context():
        plan_id = db.session.scalar(db.select(PlanSaaS.id).where(PlanSaaS.codigo == "ultra"))

    respuesta = client.patch(
        f"/api/superadmin/planes/{plan_id}",
        json={
            "limite_productos": 0,
        },
    )

    assert respuesta.status_code == 400
    assert "mayor que cero" in respuesta.get_json()["mensaje"]


def test_superadmin_edita_plan_desde_api_y_panel(app, client):
    ids = _preparar(app, client)
    app.test_cli_runner().invoke(args=["seed-planes"])
    _login(client)

    panel = client.get("/superadministracion")
    assert panel.status_code == 200
    for contrato in (
        b'id="editor-plan"',
        b'id="formulario-plan"',
        b'id="editor-plan-funciones"',
        b'id="guardar-plan"',
        b'id="total-planes-publicos"',
        b'id="total-planes-facturables"',
        b'id="total-niveles-internos"',
    ):
        assert contrato in panel.data

    with app.app_context():
        plan_id = db.session.scalar(db.select(PlanSaaS.id).where(PlanSaaS.codigo == "avanzado"))

    respuesta = client.patch(
        f"/api/superadmin/planes/{plan_id}",
        json={
            "nombre": "Avanzado Comercial",
            "descripcion": "Configuración administrada desde el panel",
            "precio_mensual": 10990,
            "precio_anual": 109900,
            "dias_prueba": 30,
            "limite_productos": 800,
            "limite_usuarios": 5,
            "limite_movimientos_mes": 8000,
            "limite_sucursales": 2,
            "limite_bodegas": 2,
            "almacenamiento_mb": 3000,
            "funciones": {"productos": True, "ia": True},
            "activo": True,
            "orden": 9,
        },
    )

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["nombre"] == "Avanzado Comercial"
    assert datos["descripcion"] == "Configuración administrada desde el panel"
    assert datos["almacenamiento_mb"] == 3000
    assert datos["dias_prueba"] == 30
    assert datos["orden"] == 9
    assert datos["funciones"]["ia"] is True
    assert datos["es_publico"] is True
    assert datos["es_facturable"] is True
    assert datos["tipo_comercial"] == "suscripcion_publica"
    assert datos["reglas_edicion"] == {
        "precios": True,
        "dias_prueba": True,
        "disponibilidad_publica": True,
    }

    # El despliegue no debe volver a sobrescribir una edición comercial.
    sembrado = app.test_cli_runner().invoke(args=["seed-planes"])
    assert sembrado.exit_code == 0
    with app.app_context():
        plan = db.session.get(PlanSaaS, plan_id)
        assert plan.nombre == "Avanzado Comercial"
        assert plan.precio_mensual == 10990
        assert plan.funciones["ia"] is False


def test_comando_crea_superadmin_con_correo_verificado(app):
    resultado = app.test_cli_runner().invoke(
        args=[
            "crear-super-admin",
            "--nombre",
            "Propietario",
            "--email",
            "propietario@nexustock.cl",
            "--password",
            "ClavePropietario123",
        ]
    )
    assert resultado.exit_code == 0
    with app.app_context():
        usuario = db.session.scalar(
            db.select(Usuario).where(Usuario.email == "propietario@nexustock.cl")
        )
        assert usuario.rol == "super_admin"
        assert usuario.email_verificado is True


def test_panel_muestra_solo_cuatro_planes_comerciales(app, client):
    _preparar(app, client)
    app.test_cli_runner().invoke(args=["seed-planes"])
    _login(client)

    respuesta = client.get("/api/superadmin/planes")
    assert respuesta.status_code == 200
    planes = respuesta.get_json()["planes"]
    publicos = {plan["codigo"] for plan in planes if plan["es_publico"]}
    internos = {plan["codigo"] for plan in planes if not plan["es_publico"]}
    facturables = {plan["codigo"] for plan in planes if plan["es_facturable"]}

    assert publicos == {"avanzado", "ultra", "profesional", "empresa"}
    assert internos == set()
    assert facturables == {"avanzado", "ultra", "profesional", "empresa"}


def test_superadmin_lista_suscripciones_sin_error(
    app,
    client,
):
    _preparar(app, client)
    _login(client)

    respuesta = client.get("/api/superadmin/suscripciones")

    assert respuesta.status_code == 200
    assert isinstance(
        respuesta.get_json()["suscripciones"],
        list,
    )


def test_superadmin_controla_solicitud_empresarial(app, client):
    _preparar(app, client)
    with app.app_context():
        solicitud = SolicitudContratoEmpresarial(
            empresa_nombre="Gran Empresa",
            contacto_nombre="Responsable",
            email="responsable@granempresa.cl",
            productos_estimados=20000,
            usuarios_estimados=25,
        )
        db.session.add(solicitud)
        db.session.commit()
        solicitud_id = solicitud.id
    _login(client)

    listado = client.get("/api/superadmin/contratos-empresariales")
    assert listado.status_code == 200
    assert listado.get_json()["solicitudes"][0]["estado"] == "nueva"

    actualizada = client.patch(
        f"/api/superadmin/contratos-empresariales/{solicitud_id}",
        json={"estado": "contactada", "observacion": "Reunión agendada"},
    )
    assert actualizada.status_code == 200
    assert actualizada.get_json()["estado"] == "contactada"


def test_no_desactiva_plan_con_suscripcion_vigente(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        plan = db.session.scalar(db.select(PlanSaaS))
        servicio = ServicioSuperAdministracion(db.session.get(Usuario, ids[0]))
        with pytest.raises(ErrorSuperAdministracion):
            servicio.editar_plan(plan.id, activo=False)


def test_jefe_no_accede_servicio_global(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        admin = db.session.scalar(db.select(Usuario).where(Usuario.empresa_id == ids[1]))
        with pytest.raises(PermissionError):
            ServicioSuperAdministracion(admin)


def test_superadmin_no_puede_operar_inventario(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        superadmin = db.session.get(Usuario, ids[0])
        from app.services.contexto import ContextoOperacion
        from app.models import Bodega

        bodega = db.session.scalar(db.select(Bodega))
        with pytest.raises(PermissionError):
            ServicioInventario(superadmin, ContextoOperacion(ids[1], bodega.sucursal, bodega))


def test_auditoria_global_filtra_empresa_sin_modificarla(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioSuperAdministracion(db.session.get(Usuario, ids[0]))
        datos = servicio.listar_auditoria(empresa_id=ids[1])
        assert datos and all(a.empresa_id == ids[1] for a in datos)
        registro = datos[0]
        registro.accion = "manipulada"
        with pytest.raises(ValueError):
            db.session.commit()
        db.session.rollback()


def test_api_superadmin_y_bloqueo_empresarial(app, client):
    ids = _preparar(app, client)
    _login(client)
    assert client.get("/api/superadmin/resumen").status_code == 200
    analitica = client.get("/api/superadmin/analitica?meses=12")
    assert analitica.status_code == 200 and len(analitica.get_json()["serie"]) == 12
    assert client.get("/api/productos").status_code == 403
    respuesta = client.post(
        f"/api/superadmin/empresas/{ids[1]}/estado",
        json={"estado": "suspendida", "motivo": "Revisión administrativa"},
    )
    assert respuesta.status_code == 200 and respuesta.get_json()["estado"] == "suspendida"


def test_jefe_no_accede_rutas_globales(app, client):
    _preparar(app, client)
    client.post(
        "/autenticacion/ingresar",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )
    assert client.get("/api/superadmin/resumen").status_code == 403


def test_cli_crea_superadmin_global(app):
    corredor = app.test_cli_runner()
    resultado = corredor.invoke(
        args=["crear-super-admin", "--nombre", "Raíz", "--email", "raiz@nexustock.cl"],
        input="ClaveRaiz123\nClaveRaiz123\n",
    )
    assert resultado.exit_code == 0
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario).where(Usuario.email == "raiz@nexustock.cl"))
        assert usuario.rol == "super_admin" and usuario.empresa_id is None


def test_superadmin_gestiona_usuarios_y_estado_sistema(app, client):
    ids = _preparar(app, client)
    _login(client)
    listado = client.get("/api/superadmin/usuarios")
    assert listado.status_code == 200
    empresarial = next(u for u in listado.get_json()["usuarios"] if u["empresa_id"] == ids[1])
    assert empresarial["nombre_completo"]
    assert empresarial["empresa"]["nombre"]
    assert "password_hash" not in empresarial and "token_verificacion_hash" not in empresarial
    desactivado = client.patch(
        f"/api/superadmin/usuarios/{empresarial['id']}/estado", json={"activo": False}
    )
    assert desactivado.status_code == 200
    assert not desactivado.get_json()["activo"]
    sistema = client.get("/api/superadmin/sistema")
    assert sistema.status_code == 200
    assert sistema.get_json()["estado"] == "operativo"
    assert "SECRET_KEY" not in sistema.get_json()
    assert client.get("/superadministracion/usuarios").status_code == 200
    assert client.get("/superadministracion/sistema").status_code == 200


def test_ubicacion_es_consentida_revocable_y_visible_al_superadmin(app, client):
    ids = _preparar(app, client)
    client.post(
        "/autenticacion/ingresar",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )
    invalida = client.patch(
        "/api/usuarios/mi-ubicacion",
        json={"consentimiento": False, "latitud": -33.45, "longitud": -70.66},
    )
    assert invalida.status_code == 400
    compartida = client.patch(
        "/api/usuarios/mi-ubicacion",
        json={
            "consentimiento": True,
            "latitud": -33.45,
            "longitud": -70.66,
            "precision_m": 18.4,
        },
    )
    assert compartida.status_code == 200 and compartida.get_json()["compartiendo"] is True
    client.post("/autenticacion/salir")
    _login(client)
    datos = client.get("/api/superadmin/usuarios").get_json()["usuarios"]
    usuario = next(u for u in datos if u["empresa_id"] == ids[1])
    assert usuario["ubicacion"]["latitud"] == -33.45
    client.post("/autenticacion/salir")
    client.post(
        "/autenticacion/ingresar",
        data={"email": REGISTRO["email"], "password": REGISTRO["password"]},
    )
    assert client.delete("/api/usuarios/mi-ubicacion").status_code == 200
    with app.app_context():
        persona = db.session.scalar(db.select(Usuario).where(Usuario.empresa_id == ids[1]))
        assert persona.ubicacion_consentida is False
        assert persona.ultima_latitud is None and persona.ultima_longitud is None


def test_superadmin_no_puede_desactivarse_si_es_el_unico(app, client):
    ids = _preparar(app, client)
    _login(client)
    respuesta = client.patch(f"/api/superadmin/usuarios/{ids[0]}/estado", json={"activo": False})
    assert respuesta.status_code == 400
    assert "propia cuenta" in respuesta.get_json()["mensaje"]


def test_propietario_corrige_suscripcion_con_motivo_y_auditoria(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioSuperAdministracion(db.session.get(Usuario, ids[0]))
        suscripcion = db.session.scalar(db.select(Suscripcion))
        actualizada = servicio.editar_suscripcion(
            suscripcion.id,
            estado="suspendida",
            renovacion_automatica=False,
            motivo="Revisión contractual solicitada por finanzas",
        )
        assert actualizada.estado == "suspendida"
        auditoria = db.session.scalar(
            db.select(Auditoria).where(Auditoria.accion == "superadmin.suscripcion_editada")
        )
        assert auditoria.datos_nuevos["motivo"] == ("Revisión contractual solicitada por finanzas")


def test_control_suscripcion_rechaza_cambio_sin_motivo(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioSuperAdministracion(db.session.get(Usuario, ids[0]))
        suscripcion = db.session.scalar(db.select(Suscripcion))
        with pytest.raises(ErrorSuperAdministracion):
            servicio.editar_suscripcion(suscripcion.id, estado="cancelada", motivo="")


def test_propietario_no_simula_renovacion_sin_mandato(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        servicio = ServicioSuperAdministracion(db.session.get(Usuario, ids[0]))
        suscripcion = db.session.scalar(db.select(Suscripcion))
        suscripcion.metodo_pago_recurrente_estado = "pendiente"
        with pytest.raises(ErrorSuperAdministracion, match="método recurrente verificado"):
            servicio.editar_suscripcion(
                suscripcion.id,
                renovacion_automatica=True,
                motivo="Corrección financiera",
            )


def test_resumen_seguridad_mide_cobertura_2fa(app, client):
    ids = _preparar(app, client)
    with app.app_context():
        resumen = ServicioSuperAdministracion(db.session.get(Usuario, ids[0])).resumen_seguridad()
        assert resumen["cuentas_privilegiadas"] >= 1
        assert 0 <= resumen["cobertura_2fa_pct"] <= 100


def test_seed_planes_sincroniza_limites_oficiales_de_ubicaciones(
    app,
):
    runner = app.test_cli_runner()
    runner.invoke(args=["seed-planes"])

    with app.app_context():
        ultra = db.session.scalar(db.select(PlanSaaS).where(PlanSaaS.codigo == "ultra"))
        profesional = db.session.scalar(db.select(PlanSaaS).where(PlanSaaS.codigo == "profesional"))
        empresa = db.session.scalar(db.select(PlanSaaS).where(PlanSaaS.codigo == "empresa"))

        ultra.limite_sucursales = 99
        ultra.limite_bodegas = 99
        profesional.limite_sucursales = 99
        profesional.limite_bodegas = 99
        empresa.limite_sucursales = None
        empresa.limite_bodegas = None

        db.session.commit()

    resultado = runner.invoke(args=["seed-planes"])

    assert resultado.exit_code == 0

    with app.app_context():
        planes = {
            plan.codigo: plan
            for plan in db.session.scalars(
                db.select(PlanSaaS).where(
                    PlanSaaS.codigo.in_(
                        (
                            "ultra",
                            "profesional",
                            "empresa",
                        )
                    )
                )
            )
        }

        assert (
            planes["ultra"].limite_sucursales,
            planes["ultra"].limite_bodegas,
        ) == (2, 3)

        assert (
            planes["profesional"].limite_sucursales,
            planes["profesional"].limite_bodegas,
        ) == (5, 10)

        assert (
            planes["empresa"].limite_sucursales,
            planes["empresa"].limite_bodegas,
        ) == (10, 25)
