from flask import Blueprint, jsonify
from sqlalchemy import text

from ...models import db

estado_bp = Blueprint("estado", __name__)


@estado_bp.get("/estado")
def estado():
    return jsonify({"estado": "correcto", "servicio": "nexustock"})


@estado_bp.get("/estado/preparacion")
def preparacion():
    """Confirma que el proceso puede atender tráfico y consultar la base de datos."""
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db.session.rollback()
        return (
            jsonify(
                {
                    "estado": "no_disponible",
                    "servicio": "nexustock",
                    "dependencia": "base_de_datos",
                }
            ),
            503,
        )
    return jsonify({"estado": "preparado", "servicio": "nexustock"})
