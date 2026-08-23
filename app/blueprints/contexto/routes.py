from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...services.auditoria import registrar_auditoria
from ...services.contexto import bodegas_autorizadas, establecer_contexto, sucursales_autorizadas
from ...models import db
from .forms import ContextoForm

contexto_bp = Blueprint("contexto", __name__, url_prefix="/contexto")


def _destino_seguro(destino: str | None) -> str | None:
    return destino if destino and destino.startswith("/") and not destino.startswith("//") else None


@contexto_bp.route("/seleccionar", methods=["GET", "POST"])
@login_required
def seleccionar():
    if current_user.rol == "super_admin":
        flash("El Super Admin no utiliza ubicaciones empresariales.", "peligro")
        return redirect(url_for("panel_superadministracion.inicio"))
    formulario = ContextoForm()
    sucursales = sucursales_autorizadas(current_user)
    formulario.sucursal_id.choices = [(s.id, s.nombre) for s in sucursales]
    sucursal_solicitada = (
        formulario.sucursal_id.data
        if formulario.sucursal_id.data
        else (sucursales[0].id if sucursales else 0)
    )
    bodegas = bodegas_autorizadas(current_user, sucursal_solicitada)
    formulario.bodega_id.choices = [(b.id, b.nombre) for b in bodegas]
    if formulario.validate_on_submit():
        try:
            contexto = establecer_contexto(
                current_user, formulario.sucursal_id.data, formulario.bodega_id.data
            )
            registrar_auditoria(
                accion="contexto.seleccionado",
                modulo="contexto",
                usuario_id=current_user.id,
                empresa_id=current_user.empresa_id,
                entidad_tipo="Bodega",
                entidad_id=contexto.bodega.id,
                datos_nuevos={"sucursal_id": contexto.sucursal.id, "bodega_id": contexto.bodega.id},
            )
            db.session.commit()
            flash("Ubicación seleccionada correctamente.", "exito")
            return redirect(
                _destino_seguro(request.args.get("siguiente")) or url_for("panel.inicio")
            )
        except PermissionError:
            flash("La ubicación seleccionada no está autorizada.", "peligro")
    return render_template("contexto/seleccionar.html", form=formulario)


@contexto_bp.get("/bodegas/<int:sucursal_id>")
@login_required
def bodegas(sucursal_id: int):
    return {
        "bodegas": [
            {"id": b.id, "nombre": b.nombre} for b in bodegas_autorizadas(current_user, sucursal_id)
        ]
    }
