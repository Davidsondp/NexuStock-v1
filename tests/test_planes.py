from app.commands import PLANES
from app.services.planes import (
    CATALOGO_CAPACIDADES,
    capacidades_del_plan,
)

CAPACIDADES_BASE = {
    "dashboard",
    "productos",
    "etiquetas_qr",
    "unidades_presentaciones",
    "inventario",
    "movimientos",
    "lotes_vencimientos",
    "proveedores",
    "clientes",
    "ventas",
    "compras",
    "alertas",
    "reportes.basicos",
    "exportacion.basica",
    "usuarios.basicos",
    "configuracion",
    "pos",
    "dte",
}

CAPACIDADES_PROFESIONALES = {
    "roles.permisos",
    "proveedores.avanzados",
    "reportes.avanzados",
    "analitica",
    "recomendaciones",
    "auditoria",
    "wms",
    "integraciones",
}

CAPACIDADES_EMPRESA = {
    "exportacion.avanzada",
    "multisucursal",
    "multibodega",
    "transferencias",
    "dashboard.ejecutivo",
    "reportes.personalizados",
    "api",
    "multiempresa",
}

TODAS_LAS_CAPACIDADES = CAPACIDADES_BASE | CAPACIDADES_PROFESIONALES | CAPACIDADES_EMPRESA | {"ia"}


def planes_por_codigo():
    return {plan["codigo"]: plan for plan in PLANES}


def test_cuatro_planes_comerciales_tienen_productos_finitos():
    planes = planes_por_codigo()

    limites_esperados = {
        "avanzado": 500,
        "ultra": 2000,
        "profesional": 5000,
        "empresa": 10000,
    }

    for codigo, limite in limites_esperados.items():
        assert planes[codigo]["limite_productos"] == limite
        assert limite > 0


def test_catalogo_cubre_toda_la_capacidad():
    codigos = [capacidad["codigo"] for capacidad in CATALOGO_CAPACIDADES]

    assert len(codigos) == len(set(codigos))
    assert set(codigos) == TODAS_LAS_CAPACIDADES

    grupos = {capacidad["grupo"] for capacidad in CATALOGO_CAPACIDADES}

    assert grupos == {
        "operacion",
        "gestion",
        "inteligencia",
        "escala",
    }


def test_catalogo_declara_estado_y_condiciones():
    catalogo = {capacidad["codigo"]: capacidad for capacidad in CATALOGO_CAPACIDADES}

    for capacidad in catalogo.values():
        assert capacidad["nombre"]
        assert capacidad["descripcion"]
        assert capacidad["estado"] in {
            "disponible",
            "proximamente",
        }

    assert catalogo["lotes_vencimientos"]["condicion"] == "segun_rubro"
    assert catalogo["ia"]["estado"] == "disponible"


def test_todos_los_planes_declaran_toda_capacidad():
    for plan in PLANES:
        funciones = plan["funciones"]

        assert set(funciones) == TODAS_LAS_CAPACIDADES
        assert all(isinstance(valor, bool) for valor in funciones.values())


def test_capacidades_base_estan_en_todos_los_planes():
    for plan in PLANES:
        funciones = plan["funciones"]

        for capacidad in CAPACIDADES_BASE:
            assert funciones[capacidad] is True


def test_plan_basico_ofrece_operacion_esencial():
    basico = planes_por_codigo()["basico"]
    funciones = basico["funciones"]

    for capacidad in CAPACIDADES_BASE:
        assert funciones[capacidad] is True

    for capacidad in CAPACIDADES_PROFESIONALES | CAPACIDADES_EMPRESA | {"ia"}:
        assert funciones[capacidad] is False


def test_plan_profesional_ofrece_control_avanzado():
    profesional = planes_por_codigo()["profesional"]
    funciones = profesional["funciones"]

    for capacidad in CAPACIDADES_BASE | CAPACIDADES_PROFESIONALES | {"exportacion.avanzada"}:
        assert funciones[capacidad] is True

    for capacidad in CAPACIDADES_EMPRESA - {
        "exportacion.avanzada",
        "multisucursal",
        "multibodega",
        "transferencias",
        "ia",
    }:
        assert funciones[capacidad] is False

    assert funciones["ia"] is True


def test_plan_empresa_ofrece_toda_capacidad_disponible():
    empresa = planes_por_codigo()["empresa"]
    funciones = empresa["funciones"]

    for capacidad in TODAS_LAS_CAPACIDADES:
        assert funciones[capacidad] is True


def test_prueba_refleja_profesional_sin_exportacion():
    planes = planes_por_codigo()
    prueba = planes["prueba"]["funciones"]
    profesional = planes["profesional"]["funciones"]

    for capacidad in CAPACIDADES_BASE | CAPACIDADES_PROFESIONALES:
        assert prueba[capacidad] is True
        assert prueba[capacidad] == profesional[capacidad]

    assert prueba["exportacion.avanzada"] is False
    assert prueba["api"] is False
    assert prueba["ia"] is False


def test_capacidades_del_plan_genera_contrato_comercial():
    profesional = planes_por_codigo()["profesional"]

    capacidades = capacidades_del_plan(profesional["funciones"])

    assert len(capacidades) == len(CATALOGO_CAPACIDADES)

    por_codigo = {capacidad["codigo"]: capacidad for capacidad in capacidades}

    assert por_codigo["productos"]["incluida"] is True
    assert por_codigo["reportes.avanzados"]["incluida"] is True
    assert por_codigo["api"]["incluida"] is False
    assert por_codigo["ia"]["estado"] == "disponible"
    assert por_codigo["ia"]["incluida"] is True
