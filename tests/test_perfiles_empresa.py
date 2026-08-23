from types import SimpleNamespace

from app.services.perfiles_empresa import (
    capacidades_empresa,
)


def _empresa(rubro, capacidades=None):
    return SimpleNamespace(
        configuracion=SimpleNamespace(
            opciones={
                "rubro": rubro,
                "capacidades": capacidades or {},
            }
        )
    )


def test_farmacia_activa_capacidades_completas():
    capacidades = capacidades_empresa(_empresa("farmacia"))

    assert capacidades["control_lotes"] is True
    assert capacidades["control_vencimientos"] is True
    assert capacidades["salida_fefo"] is True
    assert capacidades["inventario_farmaceutico"] is True


def test_botilleria_activa_lotes_sin_ser_farmacia():
    capacidades = capacidades_empresa(_empresa("botilleria"))

    assert capacidades["control_lotes"] is True
    assert capacidades["control_vencimientos"] is True
    assert capacidades["salida_fefo"] is True
    assert capacidades["inventario_farmaceutico"] is False


def test_minimarket_activa_control_de_vencimiento():
    capacidades = capacidades_empresa(_empresa("minimarket"))

    assert capacidades["control_lotes"] is True
    assert capacidades["control_vencimientos"] is True
    assert capacidades["salida_fefo"] is True


def test_general_no_activa_lotes_por_defecto():
    capacidades = capacidades_empresa(_empresa("general"))

    assert capacidades["control_lotes"] is False
    assert capacidades["control_vencimientos"] is False
    assert capacidades["salida_fefo"] is False


def test_capacidad_farmaceutica_implica_lotes():
    capacidades = capacidades_empresa(
        _empresa(
            "general",
            {
                "inventario_farmaceutico": True,
            },
        )
    )

    assert capacidades["control_lotes"] is True
    assert capacidades["control_vencimientos"] is True
    assert capacidades["salida_fefo"] is True


def test_vencimientos_implican_control_de_lotes():
    capacidades = capacidades_empresa(
        _empresa(
            "general",
            {
                "control_vencimientos": True,
            },
        )
    )

    assert capacidades["control_lotes"] is True
