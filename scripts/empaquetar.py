"""Genera un ZIP distribuible sin secretos, datos locales ni cachés."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

RAIZ = Path(__file__).resolve().parents[1]
EXCLUIR_PARTES = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "instance",
    "htmlcov",
}
EXCLUIR_NOMBRES = {".env", ".coverage"}
# Pytest y las comprobaciones de instalación pueden dejar directorios temporales
# (incluidos entornos virtuales completos) dentro de la raíz del proyecto.
EXCLUIR_PREFIJOS = ("pip-", "tmp")


def incluir(ruta: Path) -> bool:
    relativa = ruta.relative_to(RAIZ)
    return not (
        ruta.name in EXCLUIR_NOMBRES
        or any(parte in EXCLUIR_PARTES for parte in relativa.parts)
        or any(parte.startswith(EXCLUIR_PREFIJOS) for parte in relativa.parts)
        or ruta.suffix in {".pyc", ".db", ".sqlite", ".log"}
    )


def empaquetar(destino: Path) -> None:
    destino = destino.resolve()
    with ZipFile(destino, "w", ZIP_DEFLATED) as archivo:
        for ruta in sorted(RAIZ.rglob("*")):
            if ruta.is_file() and ruta.resolve() != destino and incluir(ruta):
                archivo.write(ruta, Path(RAIZ.name) / ruta.relative_to(RAIZ))


if __name__ == "__main__":
    salida = RAIZ.parent / "NexuStock-Finanzas-Seguridad-Produccion-2026-08-23.zip"
    empaquetar(salida)
    print(salida)
