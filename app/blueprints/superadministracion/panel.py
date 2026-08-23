"""Panel visual exclusivo de la Super Administración."""

from flask import Blueprint, render_template
from flask_login import login_required

from ...permisos import requerir_permiso

panel_superadministracion_bp = Blueprint(
    "panel_superadministracion",
    __name__,
    url_prefix="/superadministracion",
)


@panel_superadministracion_bp.get("")
@login_required
@requerir_permiso("superadmin.dashboard")
def inicio():
    return render_template("superadministracion/panel.html")


@panel_superadministracion_bp.get("/usuarios")
@login_required
@requerir_permiso("superadmin.usuarios")
def usuarios():
    return render_template("superadministracion/usuarios.html")


@panel_superadministracion_bp.get("/sistema")
@login_required
@requerir_permiso("superadmin.sistema")
def sistema():
    return render_template("superadministracion/sistema.html")
