"""Perfiles y capacidades funcionales por empresa."""

from __future__ import annotations

CAPACIDADES_BASE = {
    "control_lotes": False,
    "control_vencimientos": False,
    "salida_fefo": False,
    "inventario_farmaceutico": False,
}

CAPACIDADES_POR_RUBRO = {
    "general": {},
    "almacen": {},
    "minimarket": {
        "control_lotes": True,
        "control_vencimientos": True,
        "salida_fefo": True,
    },
    "botilleria": {
        "control_lotes": True,
        "control_vencimientos": True,
        "salida_fefo": True,
    },
    "ferreteria": {},
    "farmacia": {
        "control_lotes": True,
        "control_vencimientos": True,
        "salida_fefo": True,
        "inventario_farmaceutico": True,
    },
}


def normalizar_rubro(rubro) -> str:
    codigo = str(rubro or "general").strip().lower()

    if codigo not in CAPACIDADES_POR_RUBRO:
        return "general"

    return codigo


def capacidades_empresa(empresa) -> dict:
    configuracion = getattr(
        empresa,
        "configuracion",
        None,
    )
    opciones = (
        configuracion.opciones
        if configuracion
        and isinstance(
            configuracion.opciones,
            dict,
        )
        else {}
    )

    rubro = normalizar_rubro(opciones.get("rubro"))

    capacidades = {
        **CAPACIDADES_BASE,
        **CAPACIDADES_POR_RUBRO[rubro],
    }

    personalizadas = opciones.get(
        "capacidades",
        {},
    )

    if isinstance(personalizadas, dict):
        for nombre, valor in personalizadas.items():
            if nombre in capacidades:
                capacidades[nombre] = bool(valor)

    # Resuelve dependencias funcionales.
    if capacidades["inventario_farmaceutico"]:
        capacidades["control_lotes"] = True
        capacidades["control_vencimientos"] = True
        capacidades["salida_fefo"] = True

    if capacidades["salida_fefo"]:
        capacidades["control_lotes"] = True
        capacidades["control_vencimientos"] = True

    if capacidades["control_vencimientos"]:
        capacidades["control_lotes"] = True

    return {
        "rubro": rubro,
        **capacidades,
    }


def tiene_capacidad(
    empresa,
    capacidad: str,
) -> bool:
    return bool(
        capacidades_empresa(empresa).get(
            capacidad,
            False,
        )
    )
