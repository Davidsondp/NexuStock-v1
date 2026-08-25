from decimal import Decimal
from pathlib import Path

from app.services.importaciones import _decimal_local


def _contenido(ruta):
    return Path(ruta).read_text(encoding="utf-8-sig")


def test_normalizador_backend_diferencia_dinero_y_cantidad():
    casos_monetarios = {
        "3.000,00": Decimal("3000.00"),
        "3000,00": Decimal("3000.00"),
        "3000.00": Decimal("3000.00"),
        "$ 3.000": Decimal("3000"),
        "4.500,50": Decimal("4500.50"),
    }

    for entrada, esperado in casos_monetarios.items():
        assert (
            _decimal_local(
                entrada,
                monetario=True,
            )
            == esperado
        )

    assert _decimal_local(
        "3.000",
        monetario=False,
    ) == Decimal("3.000")

    assert _decimal_local(
        "3,500",
        monetario=False,
    ) == Decimal("3.500")


def test_pantallas_cargan_normalizador_antes_del_modulo():
    modulos = {
        "productos": "productos.js",
        "proveedores": "proveedores.js",
        "compras": "compras.js",
        "ventas": "ventas.js",
        "inventario": "inventario.js",
    }

    for pantalla, modulo in modulos.items():
        plantilla = _contenido(f"app/templates/panel/{pantalla}.html")

        assert "js/numeros.js" in plantilla
        assert plantilla.index("js/numeros.js") < plantilla.index(f"js/{modulo}")


def test_inputs_monetarios_aceptan_formato_chileno():
    campos = {
        "app/templates/panel/productos.html": (
            "producto-costo",
            "producto-precio",
        ),
        "app/templates/panel/proveedores.html": ("proveedor-compra-minima",),
        "app/templates/panel/inventario.html": (
            "movimiento-costo-unitario",
            "movimiento-precio-unitario",
        ),
    }

    for nombre, identificadores in campos.items():
        plantilla = _contenido(nombre)

        for identificador in identificadores:
            inicio = plantilla.index(f'id="{identificador}"')
            fragmento = plantilla[inicio : inicio + 350]

            assert 'type="text"' in fragmento
            assert 'inputmode="decimal"' in fragmento
            assert 'type="number"' not in fragmento


def test_flujo_monetario_usa_conversor_compartido():
    usos = {
        "app/static/js/productos.js": "NexuNumeros.normalizarMoneda",
        "app/static/js/proveedores.js": "NexuNumeros.numeroMoneda",
        "app/static/js/compras.js": "NexuNumeros.numeroMoneda",
        "app/static/js/ventas.js": "NexuNumeros.numeroMoneda",
        "app/static/js/inventario.js": "NexuNumeros.numeroMoneda",
    }

    for nombre, llamada in usos.items():
        assert llamada in _contenido(nombre)

    for nombre in (
        "app/static/js/compras.js",
        "app/static/js/ventas.js",
    ):
        javascript = _contenido(nombre)

        assert 'precio.type = "text"' in javascript
        assert 'precio.inputMode = "decimal"' in javascript
