"""Contexto empresarial seguro para cada solicitud autenticada."""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps

from flask import (
    abort,
    g,
    has_request_context,
    redirect,
    request,
    session,
    url_for,
)
from flask_login import current_user

from ..models import Bodega, Sucursal, UsuarioSucursal, db

CLAVE_SUCURSAL = "contexto_sucursal_id"
CLAVE_BODEGA = "contexto_bodega_id"


@dataclass(frozen=True)
class ContextoOperacion:
    empresa_id: int
    sucursal: Sucursal
    bodega: Bodega


def sucursales_autorizadas(usuario) -> list[Sucursal]:
    """Nunca recibe empresa desde formulario; la deriva del usuario."""
    if not usuario.is_authenticated or usuario.rol == "super_admin" or not usuario.empresa_id:
        return []
    sentencia = (
        db.select(Sucursal)
        .join(UsuarioSucursal, UsuarioSucursal.sucursal_id == Sucursal.id)
        .where(
            UsuarioSucursal.usuario_id == usuario.id,
            UsuarioSucursal.empresa_id == usuario.empresa_id,
            Sucursal.empresa_id == usuario.empresa_id,
            Sucursal.activa.is_(True),
            Sucursal.eliminado.is_(False),
        )
        .order_by(UsuarioSucursal.es_principal.desc(), Sucursal.nombre)
    )
    return list(db.session.scalars(sentencia).unique())


def bodegas_autorizadas(usuario, sucursal_id: int) -> list[Bodega]:
    sucursales_ids = {s.id for s in sucursales_autorizadas(usuario)}
    if sucursal_id not in sucursales_ids:
        return []
    return list(
        db.session.scalars(
            db.select(Bodega)
            .where(
                Bodega.empresa_id == usuario.empresa_id,
                Bodega.sucursal_id == sucursal_id,
                Bodega.activa.is_(True),
                Bodega.eliminado.is_(False),
            )
            .order_by(Bodega.nombre)
        )
    )


def limpiar_contexto() -> None:
    if not has_request_context():
        return

    session.pop(CLAVE_SUCURSAL, None)
    session.pop(CLAVE_BODEGA, None)
    g.pop("contexto_operacion", None)


def establecer_contexto(usuario, sucursal_id: int, bodega_id: int) -> ContextoOperacion:
    sucursal = next((s for s in sucursales_autorizadas(usuario) if s.id == sucursal_id), None)
    bodega = next((b for b in bodegas_autorizadas(usuario, sucursal_id) if b.id == bodega_id), None)
    if not sucursal or not bodega:
        limpiar_contexto()
        raise PermissionError("La sucursal o bodega no está autorizada")
    session[CLAVE_SUCURSAL] = sucursal.id
    session[CLAVE_BODEGA] = bodega.id
    contexto = ContextoOperacion(usuario.empresa_id, sucursal, bodega)
    g.contexto_operacion = contexto
    return contexto


def obtener_contexto(usuario, *, crear_automaticamente: bool = True) -> ContextoOperacion | None:
    # Se revalida siempre contra BD; g es sólo transporte dentro de la solicitud.
    try:
        sucursal_id = int(session.get(CLAVE_SUCURSAL))
        bodega_id = int(session.get(CLAVE_BODEGA))
        return establecer_contexto(usuario, sucursal_id, bodega_id)
    except (TypeError, ValueError, PermissionError):
        limpiar_contexto()

    if crear_automaticamente:
        sucursales = sucursales_autorizadas(usuario)
        if len(sucursales) == 1:
            bodegas = bodegas_autorizadas(usuario, sucursales[0].id)
            if len(bodegas) == 1:
                return establecer_contexto(usuario, sucursales[0].id, bodegas[0].id)
    return None


def requerir_contexto(funcion):
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("autenticacion.ingresar", siguiente=request.full_path))
        if current_user.rol == "super_admin":
            abort(403, description="El Super Admin no opera inventario empresarial")
        contexto = obtener_contexto(current_user)
        if not contexto:
            return redirect(url_for("contexto.seleccionar", siguiente=request.full_path))
        return funcion(*args, **kwargs)

    return envoltura
