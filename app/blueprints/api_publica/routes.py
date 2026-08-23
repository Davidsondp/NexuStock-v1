from flask import Blueprint, jsonify, request

from ...extensions import csrf
from ...services.claves_api import autenticar_clave, productos_publicos

api_publica_bp = Blueprint("api_publica", __name__, url_prefix="/api/v1")
csrf.exempt(api_publica_bp)


def _token():
    autorizacion = request.headers.get("Authorization", "")
    return autorizacion[7:].strip() if autorizacion.startswith("Bearer ") else None


@api_publica_bp.get("/productos")
def productos():
    try:
        clave = autenticar_clave(_token(), "productos:leer")
    except PermissionError as exc:
        return jsonify({"codigo": "api_no_autorizada", "mensaje": str(exc)}), 401
    datos = productos_publicos(clave)
    return jsonify(
        {
            "datos": [
                {
                    "id": p.id,
                    "codigo": p.codigo,
                    "codigo_barras": p.codigo_barras,
                    "nombre": p.nombre,
                    "categoria": p.categoria,
                    "unidad_medida": p.unidad_medida,
                    "precio_venta": str(p.precio_venta),
                }
                for p in datos
            ],
            "meta": {"cantidad": len(datos), "version": "v1"},
        }
    )
