"""Catálogo comercial único de capacidades de NexuStock."""

from __future__ import annotations

from typing import Final

CATALOGO_CAPACIDADES: Final = (
    {
        "codigo": "dashboard",
        "nombre": "Dashboard operacional",
        "descripcion": ("Resumen de inventario, actividad " "y situaciones prioritarias."),
        "grupo": "operacion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "productos",
        "nombre": "Productos y categorías",
        "descripcion": ("Catálogo empresarial con costos, " "precios y niveles de stock."),
        "grupo": "operacion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "etiquetas_qr",
        "nombre": "Códigos QR y etiquetas",
        "descripcion": (
            "Generación ilimitada de códigos QR y etiquetas "
            "de códigos de barras para los productos registrados."
        ),
        "grupo": "operacion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "unidades_presentaciones",
        "nombre": "Unidades y presentaciones",
        "descripcion": ("Compra y venta mediante unidades " "base o presentaciones comerciales."),
        "grupo": "operacion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "inventario",
        "nombre": "Inventario por bodega",
        "descripcion": ("Existencias disponibles y reservadas " "en cada ubicación autorizada."),
        "grupo": "operacion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "movimientos",
        "nombre": "Movimientos de inventario",
        "descripcion": ("Entradas, salidas, ajustes y " "devoluciones con trazabilidad."),
        "grupo": "operacion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "lotes_vencimientos",
        "nombre": "Lotes y vencimientos",
        "descripcion": ("Control de lotes, fechas de " "vencimiento y salida FEFO."),
        "grupo": "operacion",
        "estado": "disponible",
        "condicion": "segun_rubro",
    },
    {
        "codigo": "proveedores",
        "nombre": "Proveedores",
        "descripcion": ("Directorio de proveedores y datos " "comerciales esenciales."),
        "grupo": "gestion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "clientes",
        "nombre": "Clientes",
        "descripcion": ("Registro y administración de " "clientes de la empresa."),
        "grupo": "gestion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "ventas",
        "nombre": "Ventas y reservas",
        "descripcion": ("Creación, reserva, confirmación " "y cancelación de ventas."),
        "grupo": "operacion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "compras",
        "nombre": "Compras y recepciones",
        "descripcion": ("Órdenes de compra y recepción " "parcial o completa de productos."),
        "grupo": "operacion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "alertas",
        "nombre": "Alertas automáticas",
        "descripcion": ("Avisos de stock bajo, sobrestock, " "agotamiento y vencimientos."),
        "grupo": "inteligencia",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "reportes.basicos",
        "nombre": "Reportes básicos",
        "descripcion": ("Consulta de productos, stock " "y movimientos operacionales."),
        "grupo": "inteligencia",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "exportacion.basica",
        "nombre": "Exportación básica",
        "descripcion": ("Descarga de información operacional " "en formatos compatibles."),
        "grupo": "gestion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "usuarios.basicos",
        "nombre": "Usuarios básicos",
        "descripcion": ("Acceso seguro para el administrador " "y usuarios operacionales."),
        "grupo": "gestion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "configuracion",
        "nombre": "Configuración empresarial",
        "descripcion": ("Preferencias operacionales y datos " "generales de la empresa."),
        "grupo": "gestion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "roles.permisos",
        "nombre": "Roles y permisos avanzados",
        "descripcion": ("Control detallado de responsabilidades " "y accesos por usuario."),
        "grupo": "gestion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "proveedores.avanzados",
        "nombre": "Gestión avanzada de proveedores",
        "descripcion": (
            "Condiciones comerciales, tiempos " "de entrega y administración avanzada."
        ),
        "grupo": "gestion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "reportes.avanzados",
        "nombre": "Reportes avanzados",
        "descripcion": ("Análisis ampliado de inventario, " "ventas y movimientos."),
        "grupo": "inteligencia",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "analitica",
        "nombre": "Analítica operacional",
        "descripcion": ("Productos vendidos, sin movimiento, " "sobrestock y valor de inventario."),
        "grupo": "inteligencia",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "recomendaciones",
        "nombre": "Recomendaciones de compra",
        "descripcion": ("Cálculo de reposición basado en stock, " "consumo y tiempo de entrega."),
        "grupo": "inteligencia",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "exportacion.avanzada",
        "nombre": "Exportación avanzada",
        "descripcion": ("Exportaciones ampliadas para análisis " "y trabajo administrativo."),
        "grupo": "gestion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "auditoria",
        "nombre": "Auditoría empresarial",
        "descripcion": ("Trazabilidad de operaciones y acciones " "administrativas relevantes."),
        "grupo": "gestion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "multisucursal",
        "nombre": "Múltiples sucursales",
        "descripcion": ("Administración de varias sucursales " "dentro de una empresa."),
        "grupo": "escala",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "multibodega",
        "nombre": "Múltiples bodegas",
        "descripcion": ("Operación con varias bodegas " "y contextos de inventario."),
        "grupo": "escala",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "transferencias",
        "nombre": "Transferencias entre bodegas",
        "descripcion": ("Despacho y recepción controlada " "entre bodegas autorizadas."),
        "grupo": "escala",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "dashboard.ejecutivo",
        "nombre": "Dashboard ejecutivo",
        "descripcion": ("Indicadores consolidados para " "decisiones de gestión."),
        "grupo": "inteligencia",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "reportes.personalizados",
        "nombre": "Reportes personalizados",
        "descripcion": ("Capacidad de análisis adaptada " "a necesidades empresariales."),
        "grupo": "inteligencia",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "api",
        "nombre": "API e integraciones",
        "descripcion": ("Integración segura con sistemas " "y procesos externos."),
        "grupo": "escala",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "ia",
        "nombre": "Inteligencia artificial",
        "descripcion": ("Asesor inteligente para inventario, compras, ventas y decisiones."),
        "grupo": "inteligencia",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "pos",
        "nombre": "Punto de venta y cajas",
        "descripcion": "Ventas rápidas, pagos divididos, turnos y arqueo de caja.",
        "grupo": "operacion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "dte",
        "nombre": "Documentos tributarios",
        "descripcion": "Emisión idempotente mediante un proveedor certificado por el SII.",
        "grupo": "gestion",
        "estado": "disponible",
        "condicion": "requiere_proveedor_certificado",
    },
    {
        "codigo": "wms",
        "nombre": "Operación WMS",
        "descripcion": "Picking, packing, despacho, transportista y seguimiento.",
        "grupo": "operacion",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "integraciones",
        "nombre": "Integraciones comerciales",
        "descripcion": "Canales externos y webhooks empresariales idempotentes.",
        "grupo": "escala",
        "estado": "disponible",
        "condicion": None,
    },
    {
        "codigo": "multiempresa",
        "nombre": "Grupo multiempresa",
        "descripcion": "Filiales, accesos autorizados y consolidación corporativa.",
        "grupo": "escala",
        "estado": "disponible",
        "condicion": None,
    },
)


CODIGOS_CAPACIDADES: Final = frozenset(capacidad["codigo"] for capacidad in CATALOGO_CAPACIDADES)

CAPACIDADES_BASE: Final = frozenset(
    {
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
)

CAPACIDADES_PROFESIONALES: Final = frozenset(
    {
        "roles.permisos",
        "proveedores.avanzados",
        "reportes.avanzados",
        "analitica",
        "recomendaciones",
        "auditoria",
        "wms",
        "integraciones",
    }
)

CAPACIDADES_EMPRESA: Final = frozenset(
    {
        "exportacion.avanzada",
        "multisucursal",
        "multibodega",
        "transferencias",
        "dashboard.ejecutivo",
        "reportes.personalizados",
        "api",
        "ia",
        "multiempresa",
    }
)


def _matriz(*incluidas: set | frozenset) -> dict:
    habilitadas = set().union(*incluidas)

    return {codigo: codigo in habilitadas for codigo in CODIGOS_CAPACIDADES}


FUNCIONES_POR_PLAN: Final = {
    "prueba": _matriz(
        CAPACIDADES_BASE,
        CAPACIDADES_PROFESIONALES,
    ),
    "basico": _matriz(
        CAPACIDADES_BASE,
    ),
    "avanzado": _matriz(
        CAPACIDADES_BASE,
        {"roles.permisos", "reportes.avanzados", "auditoria"},
    ),
    "ultra": _matriz(
        CAPACIDADES_BASE,
        CAPACIDADES_PROFESIONALES,
        {
            "exportacion.avanzada",
            "multisucursal",
            "multibodega",
            "transferencias",
            "ia",
        },
    ),
    "profesional": _matriz(
        CAPACIDADES_BASE,
        CAPACIDADES_PROFESIONALES,
        {
            "exportacion.avanzada",
            "multisucursal",
            "multibodega",
            "transferencias",
            "ia",
        },
    ),
    "empresa": _matriz(
        CAPACIDADES_BASE,
        CAPACIDADES_PROFESIONALES,
        CAPACIDADES_EMPRESA,
    ),
    "corporativo": _matriz(
        CAPACIDADES_BASE,
        CAPACIDADES_PROFESIONALES,
        CAPACIDADES_EMPRESA,
    ),
}


def funciones_plan(codigo: str) -> dict:
    try:
        return dict(FUNCIONES_POR_PLAN[codigo])
    except KeyError as exc:
        raise ValueError(f"Plan desconocido: {codigo}") from exc


def capacidades_del_plan(
    funciones: dict | None,
) -> list[dict]:
    funciones = funciones or {}
    resultado = []

    for capacidad in CATALOGO_CAPACIDADES:
        item = dict(capacidad)
        item["incluida"] = bool(
            funciones.get(
                capacidad["codigo"],
                False,
            )
        )

        if capacidad["estado"] != "disponible":
            item["incluida"] = False

        resultado.append(item)

    return resultado
