"""Clasificación comercial única para evitar planes visibles por accidente."""

PLAN_PRUEBA_LEGADO = "prueba"
PLANES_PUBLICOS = frozenset({"avanzado", "ultra", "profesional", "empresa"})
PLANES_PAGADOS_PUBLICOS = PLANES_PUBLICOS
PLANES_AUTOSERVICIO = frozenset({"avanzado", "ultra", "profesional"})
PLANES_CONTRATO = frozenset({"empresa"})
PLANES_INTERNOS = frozenset({PLAN_PRUEBA_LEGADO, "basico", "corporativo"})
PLANES_NO_COMPRABLES = frozenset({*PLANES_INTERNOS, *PLANES_CONTRATO})
