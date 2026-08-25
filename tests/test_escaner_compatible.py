from hashlib import sha256
from pathlib import Path


def _texto(ruta):
    return Path(ruta).read_text(encoding="utf-8-sig")


def test_zxing_local_conserva_version_e_integridad():
    ruta = Path("app/static/vendor/" "zxing-browser-0.1.5.min.js")

    assert ruta.is_file()
    assert ruta.stat().st_size == 395062
    assert sha256(ruta.read_bytes()).hexdigest().upper() == (
        "B5AD3DF920738CA7ADCB74508D7E6B6A" "5B9024993FB9A0C702DA1AD8964ECA07"
    )

    licencia = Path("app/static/vendor/" "zxing-browser-LICENSE.txt")

    assert licencia.is_file()
    assert "MIT License" in _texto(licencia)


def test_pantallas_cargan_escaner_antes_del_modulo():
    pantallas = {
        "inventario": "inventario.js",
        "productos": "productos.js",
    }

    for pantalla, modulo in pantallas.items():
        plantilla = _texto(f"app/templates/panel/{pantalla}.html")

        posiciones = (
            plantilla.index("zxing-browser-0.1.5.min.js"),
            plantilla.index("js/escaner.js"),
            plantilla.index(f"js/{modulo}"),
        )

        assert posiciones == tuple(sorted(posiciones))


def test_escaner_compartido_tiene_nativo_y_alternativa():
    javascript = _texto("app/static/js/escaner.js")

    assert '"BarcodeDetector" in global' in javascript
    assert "BrowserMultiFormatReader" in javascript
    assert "decodeFromConstraints" in javascript
    assert 'ideal: "environment"' in javascript
    assert "getUserMedia" in javascript
    assert "pagehide" not in javascript


def test_modulos_usan_escaner_compartido():
    inventario = _texto("app/static/js/inventario.js")
    productos = _texto("app/static/js/escaner_productos.js")

    assert "NexuEscaner.crear" in inventario
    assert "NexuEscaner.crear" in productos

    assert "new BarcodeDetector" not in inventario
    assert "new BarcodeDetector" not in productos
    assert "getUserMedia" not in inventario
    assert "getUserMedia" not in productos

    assert '"pagehide"' in productos
