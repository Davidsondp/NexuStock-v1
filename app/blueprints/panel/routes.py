"""Panel visual de usuarios empresariales."""

from flask import Blueprint, current_app, g, render_template
from flask_login import current_user, login_required

from ...permisos import evaluar_permiso, requerir_permiso
from ...services.contexto import requerir_contexto
from ...services.perfiles_empresa import capacidades_empresa
from ...services.unidades_medida import unidades_sugeridas

panel_bp = Blueprint(
    "panel",
    __name__,
    url_prefix="/panel",
)


@panel_bp.get("")
@login_required
@requerir_permiso("dashboard.ver")
@requerir_contexto
def inicio():
    empresa_id = current_user.empresa_id
    return render_template(
        "panel/inicio.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        puede_ver_transferencias=evaluar_permiso(
            current_user,
            "transferencias.ver",
            empresa_id=current_user.empresa_id,
        ).permitido,
        permisos_dashboard={
            "movimiento": evaluar_permiso(
                current_user, "stock.entrada", empresa_id=empresa_id
            ).permitido
            or evaluar_permiso(current_user, "stock.salida", empresa_id=empresa_id).permitido,
            "ventas": evaluar_permiso(current_user, "ventas.ver", empresa_id=empresa_id).permitido,
            "compras": evaluar_permiso(
                current_user, "compras.ver", empresa_id=empresa_id
            ).permitido,
            "ia": evaluar_permiso(current_user, "ia.ver", empresa_id=empresa_id).permitido,
            "reportes": evaluar_permiso(
                current_user, "reportes.ver", empresa_id=empresa_id
            ).permitido,
        },
    )


@panel_bp.get("/productos")
@login_required
@requerir_permiso("productos.ver")
@requerir_contexto
def productos():
    empresa_id = current_user.empresa_id

    permisos = {
        "crear": evaluar_permiso(
            current_user,
            "productos.crear",
            empresa_id=empresa_id,
        ).permitido,
        "editar": evaluar_permiso(
            current_user,
            "productos.editar",
            empresa_id=empresa_id,
        ).permitido,
        "eliminar": evaluar_permiso(
            current_user,
            "productos.eliminar",
            empresa_id=empresa_id,
        ).permitido,
        "importar": evaluar_permiso(
            current_user,
            "productos.importar",
            empresa_id=empresa_id,
        ).permitido,
    }

    capacidades = capacidades_empresa(current_user.empresa)

    unidades = unidades_sugeridas(capacidades["rubro"])

    return render_template(
        "panel/productos.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
        capacidades=capacidades,
        unidades_sugeridas=unidades,
    )


@panel_bp.get("/productos/<int:producto_id>/imagenes")
@login_required
@requerir_permiso("productos.ver")
@requerir_contexto
def imagenes_producto(producto_id):
    from ...services.productos import ServicioProductos

    producto = ServicioProductos(current_user).obtener(producto_id)
    puede_editar = evaluar_permiso(
        current_user, "productos.editar", empresa_id=current_user.empresa_id
    ).permitido
    return render_template(
        "panel/imagenes_producto.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        producto=producto,
        puede_editar=puede_editar,
    )


@panel_bp.get("/proveedores")
@login_required
@requerir_permiso("proveedores.ver")
@requerir_contexto
def proveedores():
    empresa_id = current_user.empresa_id

    permisos = {
        "crear": evaluar_permiso(
            current_user,
            "proveedores.crear",
            empresa_id=empresa_id,
        ).permitido,
        "editar": evaluar_permiso(
            current_user,
            "proveedores.editar",
            empresa_id=empresa_id,
        ).permitido,
        "eliminar": evaluar_permiso(
            current_user,
            "proveedores.eliminar",
            empresa_id=empresa_id,
        ).permitido,
    }

    return render_template(
        "panel/proveedores.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
    )


@panel_bp.get("/compras")
@login_required
@requerir_permiso("compras.ver")
@requerir_contexto
def compras():
    empresa_id = current_user.empresa_id

    permisos = {
        "crear": evaluar_permiso(
            current_user,
            "compras.crear",
            empresa_id=empresa_id,
        ).permitido,
        "editar": evaluar_permiso(
            current_user,
            "compras.editar",
            empresa_id=empresa_id,
        ).permitido,
        "enviar": evaluar_permiso(
            current_user,
            "compras.enviar",
            empresa_id=empresa_id,
        ).permitido,
        "recibir": evaluar_permiso(
            current_user,
            "compras.recibir",
            empresa_id=empresa_id,
        ).permitido,
        "cancelar": evaluar_permiso(
            current_user,
            "compras.cancelar",
            empresa_id=empresa_id,
        ).permitido,
    }

    return render_template(
        "panel/compras.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
    )


@panel_bp.get("/ventas")
@login_required
@requerir_permiso("ventas.ver")
@requerir_contexto
def ventas():
    empresa_id = current_user.empresa_id

    permisos = {
        "crear": evaluar_permiso(
            current_user,
            "ventas.crear",
            empresa_id=empresa_id,
        ).permitido,
        "reservar": evaluar_permiso(
            current_user,
            "ventas.reservar",
            empresa_id=empresa_id,
        ).permitido,
        "confirmar": evaluar_permiso(
            current_user,
            "ventas.confirmar",
            empresa_id=empresa_id,
        ).permitido,
        "cancelar": evaluar_permiso(
            current_user,
            "ventas.cancelar",
            empresa_id=empresa_id,
        ).permitido,
    }

    return render_template(
        "panel/ventas.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
    )


@panel_bp.get("/clientes")
@login_required
@requerir_permiso("clientes.ver")
@requerir_contexto
def clientes():
    empresa_id = current_user.empresa_id

    permisos = {
        "crear": evaluar_permiso(
            current_user,
            "clientes.crear",
            empresa_id=empresa_id,
        ).permitido,
        "editar": evaluar_permiso(
            current_user,
            "clientes.editar",
            empresa_id=empresa_id,
        ).permitido,
        "eliminar": evaluar_permiso(
            current_user,
            "clientes.eliminar",
            empresa_id=empresa_id,
        ).permitido,
    }

    return render_template(
        "panel/clientes.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
    )


@panel_bp.get("/inventario")
@login_required
@requerir_permiso("stock.ver")
@requerir_contexto
def inventario():
    empresa_id = current_user.empresa_id

    permisos = {
        "entrada": evaluar_permiso(
            current_user,
            "stock.entrada",
            empresa_id=empresa_id,
        ).permitido,
        "salida": evaluar_permiso(
            current_user,
            "stock.salida",
            empresa_id=empresa_id,
        ).permitido,
        "ajuste": evaluar_permiso(
            current_user,
            "stock.ajuste",
            empresa_id=empresa_id,
        ).permitido,
        "devolucion": evaluar_permiso(
            current_user,
            "stock.devolucion",
            empresa_id=empresa_id,
        ).permitido,
    }

    capacidades = capacidades_empresa(current_user.empresa)

    return render_template(
        "panel/inventario.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
        capacidades=capacidades,
    )


@panel_bp.get("/transferencias")
@login_required
@requerir_permiso("transferencias.ver")
@requerir_contexto
def transferencias():
    empresa_id = current_user.empresa_id
    permisos = {
        "crear": evaluar_permiso(
            current_user, "transferencias.crear", empresa_id=empresa_id
        ).permitido,
        "despachar": evaluar_permiso(
            current_user, "transferencias.despachar", empresa_id=empresa_id
        ).permitido,
        "recibir": evaluar_permiso(
            current_user, "transferencias.recibir", empresa_id=empresa_id
        ).permitido,
    }
    return render_template(
        "panel/transferencias.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
    )


@panel_bp.get("/alertas")
@login_required
@requerir_permiso("alertas.ver")
@requerir_contexto
def alertas():
    empresa_id = current_user.empresa_id

    permisos = {
        "gestionar": evaluar_permiso(
            current_user,
            "alertas.gestionar",
            empresa_id=empresa_id,
        ).permitido,
    }

    return render_template(
        "panel/alertas.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
    )


@panel_bp.get("/reportes")
@login_required
@requerir_permiso("reportes.ver")
@requerir_contexto
def reportes():
    empresa_id = current_user.empresa_id

    permisos = {
        "analitica": evaluar_permiso(
            current_user,
            "analitica.ver",
            empresa_id=empresa_id,
        ).permitido,
        "exportar": evaluar_permiso(
            current_user,
            "reportes.exportar",
            empresa_id=empresa_id,
        ).permitido,
        "ejecutivo": evaluar_permiso(
            current_user,
            "dashboard.ejecutivo",
            empresa_id=empresa_id,
        ).permitido,
    }

    return render_template(
        "panel/reportes.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
    )


@panel_bp.get("/administracion/usuarios")
@login_required
@requerir_permiso("usuarios.ver")
@requerir_contexto
def administracion_usuarios():
    empresa_id = current_user.empresa_id

    permisos = {
        "crear": evaluar_permiso(
            current_user,
            "usuarios.crear",
            empresa_id=empresa_id,
        ).permitido,
        "editar": evaluar_permiso(
            current_user,
            "usuarios.editar",
            empresa_id=empresa_id,
        ).permitido,
        "desactivar": evaluar_permiso(
            current_user,
            "usuarios.desactivar",
            empresa_id=empresa_id,
        ).permitido,
        "roles": evaluar_permiso(
            current_user,
            "usuarios.gestionar_roles",
            empresa_id=empresa_id,
        ).permitido,
    }

    suscripcion = current_user.empresa.suscripcion_actual
    limite_usuarios = suscripcion.plan.limite_usuarios if suscripcion else 0

    from ...permisos import (
        permisos_empresariales_conocidos,
    )

    return render_template(
        "panel/usuarios.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
        limite_usuarios=limite_usuarios,
        permisos_catalogo=sorted(permisos_empresariales_conocidos()),
    )


@panel_bp.get("/administracion/planes")
@login_required
@requerir_permiso("suscripciones.ver")
@requerir_contexto
def administracion_planes():
    contexto = g.contexto_operacion

    puede_solicitar = evaluar_permiso(
        current_user,
        "suscripciones.solicitar",
    ).permitido

    return render_template(
        "panel/planes.html",
        contexto=contexto,
        puede_solicitar=puede_solicitar,
    )


@panel_bp.get("/administracion/ubicaciones")
@login_required
@requerir_permiso("empresa.editar")
@requerir_contexto
def administracion_ubicaciones():
    empresa_id = current_user.empresa_id

    permisos = {
        "crear_sucursal": evaluar_permiso(
            current_user,
            "sucursales.crear",
            empresa_id=empresa_id,
        ).permitido,
        "editar_sucursal": evaluar_permiso(
            current_user,
            "sucursales.editar",
            empresa_id=empresa_id,
        ).permitido,
        "desactivar_sucursal": evaluar_permiso(
            current_user,
            "sucursales.desactivar",
            empresa_id=empresa_id,
        ).permitido,
        "crear_bodega": evaluar_permiso(
            current_user,
            "bodegas.crear",
            empresa_id=empresa_id,
        ).permitido,
        "editar_bodega": evaluar_permiso(
            current_user,
            "bodegas.editar",
            empresa_id=empresa_id,
        ).permitido,
        "desactivar_bodega": evaluar_permiso(
            current_user,
            "bodegas.desactivar",
            empresa_id=empresa_id,
        ).permitido,
        "asignar_usuarios": evaluar_permiso(
            current_user,
            "usuarios.editar",
            empresa_id=empresa_id,
        ).permitido,
    }

    suscripcion = current_user.empresa.suscripcion_actual
    plan = suscripcion.plan if suscripcion else None

    limite_sucursales = plan.limite_sucursales if plan else 0
    limite_bodegas = plan.limite_bodegas if plan else 0

    return render_template(
        "panel/ubicaciones.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
        limite_sucursales=limite_sucursales,
        limite_bodegas=limite_bodegas,
    )


@panel_bp.get("/administracion/configuracion")
@login_required
@requerir_permiso("configuracion.ver")
@requerir_contexto
def administracion_configuracion():
    empresa_id = current_user.empresa_id
    permisos = {
        "empresa": evaluar_permiso(current_user, "empresa.editar", empresa_id=empresa_id).permitido,
        "preferencias": evaluar_permiso(
            current_user, "configuracion.editar", empresa_id=empresa_id
        ).permitido,
    }
    return render_template(
        "panel/configuracion.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
        permisos=permisos,
    )


@panel_bp.get("/importaciones")
@login_required
@requerir_permiso("productos.importar")
@requerir_contexto
def importaciones():
    return render_template(
        "panel/importaciones.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
    )


@panel_bp.get("/ayuda")
@login_required
def ayuda():
    return render_template(
        "panel/ayuda.html",
        soporte_email=current_app.config["SOPORTE_EMAIL"],
        puede_importar=evaluar_permiso(
            current_user,
            "productos.importar",
            empresa_id=current_user.empresa_id,
        ).permitido,
    )


@panel_bp.get("/administracion/auditoria")
@login_required
@requerir_permiso("auditoria.ver")
@requerir_contexto
def administracion_auditoria():
    return render_template(
        "panel/auditoria.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
    )


@panel_bp.get("/notificaciones")
@login_required
@requerir_permiso("dashboard.ver")
@requerir_contexto
def notificaciones():
    return render_template("panel/notificaciones.html", contexto=g.contexto_operacion)


@panel_bp.get("/administracion/claves-api")
@login_required
@requerir_permiso("api.gestionar")
@requerir_contexto
def administracion_claves_api():
    return render_template("panel/claves_api.html", contexto=g.contexto_operacion)


@panel_bp.get("/reportes-personalizados")
@login_required
@requerir_permiso("reportes.personalizados")
@requerir_contexto
def reportes_personalizados():
    return render_template("panel/reportes_personalizados.html", contexto=g.contexto_operacion)


@panel_bp.get("/asistente")
@login_required
@requerir_permiso("ia.ver")
@requerir_contexto
def asistente():
    return render_template(
        "panel/asistente_ia.html",
        empresa=current_user.empresa,
        contexto=g.contexto_operacion,
    )
