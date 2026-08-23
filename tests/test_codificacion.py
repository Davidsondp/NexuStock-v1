"""Evita que vuelvan a versionarse textos españoles dañados."""

from pathlib import Path
import re

RAICES = ("app", "tests", "migrations", "docs")
EXTENSIONES = {".py", ".js", ".css", ".html", ".md", ".yaml", ".yml"}
PATRONES_CORRUPTOS = (
    re.compile(r"Ã|Â|�"),
    re.compile(
        r"presentaci\?n|v\?lid|c\?digo|conversi\?n|contrase\?a|"
        r"identificaci\?n|direcci\?n|recepci\?n|producci\?n|"
        r"configuraci\?n|autom\?ticamente|n\?mero|pr\?xim|\?rdenes"
    ),
)


def test_repositorio_no_contiene_mojibake():
    errores = []
    for raiz in RAICES:
        for ruta in Path(raiz).rglob("*"):
            if (
                not ruta.is_file()
                or ruta.suffix not in EXTENSIONES
                or ruta.resolve() == Path(__file__).resolve()
            ):
                continue
            contenido = ruta.read_text(encoding="utf-8-sig")
            for numero, linea in enumerate(contenido.splitlines(), 1):
                if any(patron.search(linea) for patron in PATRONES_CORRUPTOS):
                    errores.append(f"{ruta}:{numero}: {linea.strip()}")
    assert not errores, "Textos dañados detectados:\n" + "\n".join(errores)
