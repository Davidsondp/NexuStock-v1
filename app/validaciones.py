"""Normalización central de identificadores y datos de contacto."""

import re


def normalizar_rut(valor, *, obligatorio=False):
    texto = str(valor or "").strip().upper()
    if not texto:
        if obligatorio:
            raise ValueError("El RUT es obligatorio")
        return None
    limpio = re.sub(r"[^0-9K]", "", texto)
    if len(limpio) < 2 or not limpio[:-1].isdigit() or limpio[-1] not in "0123456789K":
        raise ValueError("El RUT no tiene un formato válido")
    cuerpo = limpio[:-1].lstrip("0") or "0"
    suma, multiplicador = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = multiplicador + 1 if multiplicador < 7 else 2
    resultado = 11 - suma % 11
    esperado = "0" if resultado == 11 else "K" if resultado == 10 else str(resultado)
    if limpio[-1] != esperado:
        raise ValueError("El dígito verificador del RUT no es válido")
    miles = f"{int(cuerpo):,}".replace(",", ".")
    return f"{miles}-{esperado}"


def normalizar_telefono(valor, *, obligatorio=False):
    texto = str(valor or "").strip()
    if not texto:
        if obligatorio:
            raise ValueError("El teléfono es obligatorio")
        return None
    extension = ""
    coincidencia = re.search(r"(?:ext\.?|anexo)\s*(\d{1,6})$", texto, re.IGNORECASE)
    if coincidencia:
        extension = f" ext. {coincidencia.group(1)}"
        texto = texto[: coincidencia.start()]
    tiene_mas = texto.lstrip().startswith("+")
    digitos = re.sub(r"\D", "", texto)
    if len(digitos) == 9 and digitos.startswith("9"):
        digitos, tiene_mas = "56" + digitos, True
    if not 8 <= len(digitos) <= 15:
        raise ValueError("El teléfono debe contener entre 8 y 15 dígitos")
    return ("+" if tiene_mas else "") + digitos + extension
