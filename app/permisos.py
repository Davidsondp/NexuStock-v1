"""Autorización central de NexuStock.

El permiso efectivo exige, en este orden: usuario válido, ámbito correcto,
empresa activa, suscripción vigente, permiso de rol y función contratada.
Los permisos especiales pueden negar o conceder dentro del plan, nunca ampliar
las funciones comerciales del plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Callable, Final

from flask import abort, jsonify, request
from flask_login import current_user

ROLES: Final = frozenset({"super_admin", "jefe", "supervisor", "empleado"})
ROLES_EMPRESA: Final = frozenset({"jefe", "supervisor", "empleado"})

PERMISOS_ROL: Final[dict[str, frozenset[str]]] = {
    "jefe": frozenset(
        {
            "dashboard.ver",
            "dashboard.ejecutivo",
            "productos.ver",
            "productos.crear",
            "productos.editar",
            "productos.eliminar",
            "productos.exportar",
            "productos.importar",
            "stock.ver",
            "stock.entrada",
            "stock.salida",
            "stock.ajuste",
            "stock.devolucion",
            "stock.transferencia",
            "movimientos.ver",
            "movimientos.exportar",
            "proveedores.ver",
            "proveedores.crear",
            "proveedores.editar",
            "proveedores.eliminar",
            "clientes.ver",
            "clientes.crear",
            "clientes.editar",
            "clientes.eliminar",
            "compras.ver",
            "compras.crear",
            "compras.editar",
            "compras.enviar",
            "compras.recibir",
            "compras.cancelar",
            "reportes.ver",
            "reportes.avanzados",
            "ventas.ver",
            "ventas.crear",
            "ventas.reservar",
            "ventas.confirmar",
            "ventas.cancelar",
            "reportes.exportar",
            "reportes.personalizados",
            "analitica.ver",
            "ia.ver",
            "usuarios.ver",
            "usuarios.crear",
            "usuarios.editar",
            "usuarios.desactivar",
            "usuarios.gestionar_roles",
            "auditoria.ver",
            "alertas.ver",
            "alertas.gestionar",
            "sucursales.ver",
            "sucursales.crear",
            "sucursales.editar",
            "sucursales.desactivar",
            "bodegas.ver",
            "bodegas.crear",
            "bodegas.editar",
            "bodegas.desactivar",
            "transferencias.ver",
            "transferencias.crear",
            "transferencias.despachar",
            "transferencias.recibir",
            "configuracion.ver",
            "configuracion.editar",
            "empresa.ver",
            "empresa.editar",
            "api.gestionar",
            "suscripciones.ver",
            "suscripciones.solicitar",
            "multiempresa.ver",
            "pos.operar",
            "wms.operar",
            "dte.emitir",
            "integraciones.gestionar",
        }
    ),
    "supervisor": frozenset(
        {
            "dashboard.ver",
            "productos.ver",
            "productos.crear",
            "productos.editar",
            "productos.exportar",
            "stock.ver",
            "stock.entrada",
            "stock.salida",
            "stock.ajuste",
            "stock.devolucion",
            "stock.transferencia",
            "movimientos.ver",
            "movimientos.exportar",
            "proveedores.ver",
            "proveedores.crear",
            "proveedores.editar",
            "clientes.ver",
            "clientes.crear",
            "clientes.editar",
            "compras.ver",
            "compras.crear",
            "compras.editar",
            "compras.enviar",
            "compras.recibir",
            "reportes.ver",
            "reportes.avanzados",
            "reportes.exportar",
            "ventas.ver",
            "ventas.crear",
            "ventas.reservar",
            "ventas.confirmar",
            "ventas.cancelar",
            "analitica.ver",
            "ia.ver",
            "alertas.ver",
            "alertas.gestionar",
            "sucursales.ver",
            "bodegas.ver",
            "transferencias.ver",
            "transferencias.crear",
            "transferencias.despachar",
            "transferencias.recibir",
            "multiempresa.ver",
            "pos.operar",
            "wms.operar",
            "dte.emitir",
        }
    ),
    "empleado": frozenset(
        {
            "dashboard.ver",
            "productos.ver",
            "stock.ver",
            "stock.entrada",
            "stock.salida",
            "stock.devolucion",
            "movimientos.ver",
            "proveedores.ver",
            "clientes.ver",
            "clientes.crear",
            "clientes.editar",
            "compras.ver",
            "ventas.ver",
            "ventas.crear",
            "ventas.reservar",
            "ventas.confirmar",
            "ventas.cancelar",
            "alertas.ver",
            "sucursales.ver",
            "bodegas.ver",
            "transferencias.ver",
            "pos.operar",
            "wms.operar",
        }
    ),
    "super_admin": frozenset(
        {
            "superadmin.dashboard",
            "superadmin.empresas",
            "superadmin.usuarios",
            "superadmin.planes",
            "superadmin.suscripciones",
            "superadmin.pagos",
            "superadmin.auditoria",
            "superadmin.sistema",
        }
    ),
}

# Función del plan requerida por cada permiso comercial. Lo omitido es básico
# y sólo exige una suscripción vigente.
FUNCION_POR_PERMISO: Final[dict[str, str]] = {
    "dashboard.ejecutivo": "dashboard.ejecutivo",
    "productos.importar": "exportacion.avanzada",
    "reportes.exportar": "exportacion.basica",
    "usuarios.gestionar_roles": "roles.permisos",
    "stock.transferencia": "transferencias",
    "proveedores.eliminar": "proveedores.avanzados",
    "reportes.avanzados": "reportes.avanzados",
    "reportes.personalizados": "reportes.personalizados",
    "analitica.ver": "analitica",
    "ia.ver": "ia",
    "auditoria.ver": "auditoria",
    "sucursales.crear": "multisucursal",
    "sucursales.editar": "multisucursal",
    "sucursales.desactivar": "multisucursal",
    "bodegas.crear": "multibodega",
    "bodegas.editar": "multibodega",
    "bodegas.desactivar": "multibodega",
    "transferencias.crear": "transferencias",
    "transferencias.despachar": "transferencias",
    "transferencias.recibir": "transferencias",
    "api.gestionar": "api",
    "multiempresa.ver": "multiempresa",
    "pos.operar": "pos",
    "wms.operar": "wms",
    "dte.emitir": "dte",
    "integraciones.gestionar": "integraciones",
}


@dataclass(frozen=True)
class DecisionAcceso:
    permitido: bool
    codigo: str
    mensaje: str


def _decision(permitido: bool, codigo: str, mensaje: str) -> DecisionAcceso:
    return DecisionAcceso(permitido, codigo, mensaje)


def evaluar_permiso(usuario, permiso: str, *, empresa_id: int | None = None) -> DecisionAcceso:
    """Autoridad única. No confía en un empresa_id proveniente del frontend."""
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return _decision(False, "no_autenticado", "Debes iniciar sesión")
    if not getattr(usuario, "is_active", False):
        return _decision(False, "usuario_inactivo", "Usuario inactivo o bloqueado")
    rol = getattr(usuario, "rol", None)
    if rol not in ROLES:
        return _decision(False, "rol_invalido", "Rol no reconocido")

    if rol == "super_admin":
        permitido = permiso in PERMISOS_ROL["super_admin"]
        return _decision(
            permitido,
            "permitido" if permitido else "ambito_invalido",
            "Acceso autorizado" if permitido else "El Super Admin no opera datos empresariales",
        )

    usuario_empresa_id = getattr(usuario, "empresa_id", None)
    if usuario_empresa_id is None or (empresa_id is not None and empresa_id != usuario_empresa_id):
        return _decision(False, "empresa_invalida", "Acceso fuera del ámbito empresarial")
    empresa = getattr(usuario, "empresa", None)
    if not empresa or not empresa.esta_activa():
        return _decision(False, "empresa_inactiva", "Empresa inactiva")
    suscripcion = empresa.suscripcion_actual
    if not suscripcion:
        if (
            rol == "jefe"
            and permiso in {"suscripciones.ver", "suscripciones.solicitar"}
            and permiso in PERMISOS_ROL[rol]
            and (getattr(usuario, "permisos_especiales", None) or {}).get(permiso) is not False
        ):
            return _decision(True, "renovacion_requerida", "Acceso autorizado para renovar")
        return _decision(False, "suscripcion_inactiva", "No existe una suscripción vigente")

    permisos = PERMISOS_ROL[rol]
    especiales = getattr(usuario, "permisos_especiales", None) or {}
    if especiales.get(permiso) is False:
        return _decision(False, "denegado_explicito", "Permiso denegado expresamente")
    if permiso not in permisos and especiales.get(permiso) is not True:
        return _decision(False, "permiso_insuficiente", "El rol no posee este permiso")

    funcion = FUNCION_POR_PERMISO.get(permiso)
    funcion_disponible = not funcion or suscripcion.plan.tiene_funcion(funcion)
    if funcion == "exportacion.basica":
        funcion_disponible = funcion_disponible or suscripcion.plan.tiene_funcion(
            "exportacion.avanzada"
        )
    if funcion == "roles.permisos" and suscripcion.plan.codigo == "prueba":
        # La prueba comercial incluye las funciones del plan Profesional.
        funcion_disponible = True
    if not funcion_disponible:
        return _decision(False, "plan_insuficiente", "La función no está incluida en el plan")
    return _decision(True, "permitido", "Acceso autorizado")


def tiene_permiso(usuario, permiso: str, *, empresa_id: int | None = None) -> bool:
    return evaluar_permiso(usuario, permiso, empresa_id=empresa_id).permitido


def requerir_permiso(permiso: str) -> Callable:
    def decorador(funcion: Callable) -> Callable:
        @wraps(funcion)
        def envoltura(*args, **kwargs):
            decision = evaluar_permiso(current_user, permiso)
            if decision.permitido:
                return funcion(*args, **kwargs)
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"codigo": decision.codigo, "mensaje": decision.mensaje}), 403
            abort(403, description=decision.mensaje)

        return envoltura

    return decorador


def exigir_misma_empresa(usuario, entidad) -> None:
    """Protección IDOR reutilizable para servicios y rutas empresariales."""
    if getattr(usuario, "rol", None) == "super_admin":
        raise PermissionError("El Super Admin no opera entidades empresariales")
    if getattr(entidad, "empresa_id", None) != getattr(usuario, "empresa_id", None):
        raise PermissionError("La entidad no pertenece a la empresa del usuario")


def permisos_empresariales_conocidos() -> frozenset[str]:
    """Catálogo único para validar permisos especiales administrables."""
    return frozenset().union(
        *(permisos for rol, permisos in PERMISOS_ROL.items() if rol != "super_admin")
    )
