from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...catalogo_planes import PLANES_PUBLICOS
from ...permisos import requerir_permiso
from ...services.superadministracion import ErrorSuperAdministracion, ServicioSuperAdministracion

superadministracion_bp = Blueprint("superadministracion", __name__, url_prefix="/api/superadmin")


def _error(exc):
    return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400


def _empresa(e):
    return {
        "id": e.id,
        "nombre": e.nombre,
        "email": e.email,
        "telefono": e.telefono,
        "direccion": e.direccion,
        "ciudad": e.ciudad,
        "pais": e.pais,
        "identificacion_fiscal": e.identificacion_fiscal,
        "estado": e.estado,
        "motivo_suspension": e.motivo_suspension,
    }


def _plan(p):
    es_publico = p.codigo in PLANES_PUBLICOS
    es_prueba = p.codigo in {"avanzado", "ultra", "profesional", "empresa"}
    es_facturable = p.codigo in {"avanzado", "ultra", "profesional", "empresa"}
    tipo = {
        "prueba": "compatibilidad_interna",
        "empresa": "contrato_empresarial",
        "basico": "compatibilidad_interna",
        "corporativo": "contrato_interno",
    }.get(p.codigo, "suscripcion_publica")
    return {
        "id": p.id,
        "codigo": p.codigo,
        "nombre": p.nombre,
        "descripcion": p.descripcion,
        "precio_mensual": str(p.precio_mensual),
        "precio_anual": str(p.precio_anual),
        "moneda": p.moneda,
        "dias_prueba": p.dias_prueba,
        "limite_productos": p.limite_productos,
        "limite_usuarios": p.limite_usuarios,
        "limite_movimientos_mes": p.limite_movimientos_mes,
        "limite_sucursales": p.limite_sucursales,
        "limite_bodegas": p.limite_bodegas,
        "almacenamiento_mb": p.almacenamiento_mb,
        "funciones": p.funciones,
        "activo": p.activo,
        "orden": p.orden,
        "es_publico": es_publico,
        "es_facturable": es_facturable,
        "tipo_comercial": tipo,
        "reglas_edicion": {
            "precios": es_facturable,
            "dias_prueba": es_prueba,
            "disponibilidad_publica": es_publico,
        },
    }


@superadministracion_bp.get("/resumen")
@login_required
@requerir_permiso("superadmin.dashboard")
def resumen():
    return jsonify(ServicioSuperAdministracion(current_user).resumen())


@superadministracion_bp.get("/analitica")
@login_required
@requerir_permiso("superadmin.dashboard")
def analitica():
    try:
        return jsonify(
            ServicioSuperAdministracion(current_user).analitica(meses=request.args.get("meses", 12))
        )
    except ErrorSuperAdministracion as exc:
        return _error(exc)


@superadministracion_bp.get("/empresas")
@login_required
@requerir_permiso("superadmin.empresas")
def empresas():
    try:
        return jsonify(
            {
                "empresas": [
                    _empresa(e)
                    for e in ServicioSuperAdministracion(current_user).listar_empresas(
                        estado=request.args.get("estado"), buscar=request.args.get("buscar")
                    )
                ]
            }
        )
    except ErrorSuperAdministracion as exc:
        return _error(exc)


@superadministracion_bp.post("/empresas/<int:empresa_id>/estado")
@login_required
@requerir_permiso("superadmin.empresas")
def cambiar_estado_empresa(empresa_id):
    try:
        d = request.get_json(silent=True) or {}
        return jsonify(
            _empresa(
                ServicioSuperAdministracion(current_user).cambiar_estado_empresa(
                    empresa_id, estado=d.get("estado"), motivo=d.get("motivo")
                )
            )
        )
    except ErrorSuperAdministracion as exc:
        return _error(exc)


@superadministracion_bp.get("/planes")
@login_required
@requerir_permiso("superadmin.planes")
def planes():
    return jsonify(
        {"planes": [_plan(p) for p in ServicioSuperAdministracion(current_user).listar_planes()]}
    )


@superadministracion_bp.patch("/planes/<int:plan_id>")
@login_required
@requerir_permiso("superadmin.planes")
def editar_plan(plan_id):
    try:
        return jsonify(
            _plan(
                ServicioSuperAdministracion(current_user).editar_plan(
                    plan_id, **(request.get_json(silent=True) or {})
                )
            )
        )
    except ErrorSuperAdministracion as exc:
        return _error(exc)


@superadministracion_bp.get("/suscripciones")
@login_required
@requerir_permiso("superadmin.suscripciones")
def suscripciones():
    datos = ServicioSuperAdministracion(current_user).listar_suscripciones(
        empresa_id=request.args.get("empresa_id", type=int),
        estado=request.args.get("estado"),
    )
    return jsonify(
        {
            "suscripciones": [
                {
                    "id": s.id,
                    "empresa_id": s.empresa_id,
                    "plan_id": s.plan_id,
                    "estado": s.estado,
                    "ciclo": s.ciclo,
                    "fecha_inicio": s.fecha_inicio.isoformat(),
                    "fecha_fin": (
                        s.fecha_fin.isoformat()
                        if s.fecha_fin
                        else None
                    ),
                    "renovacion_automatica": (
                        s.renovacion_automatica
                    ),
                    "cancelar_al_fin_periodo": (
                        s.cancelar_al_fin_periodo
                    ),
                    "proveedor_cobro": s.proveedor_cobro,
                }
                for s in datos
            ]
        }
    )


def _contrato_empresarial(solicitud):
    return {
        "id": solicitud.id,
        "empresa_nombre": solicitud.empresa_nombre,
        "contacto_nombre": solicitud.contacto_nombre,
        "email": solicitud.email,
        "telefono": solicitud.telefono,
        "productos_estimados": solicitud.productos_estimados,
        "usuarios_estimados": solicitud.usuarios_estimados,
        "mensaje": solicitud.mensaje,
        "estado": solicitud.estado,
        "observacion_interna": solicitud.observacion_interna,
        "creado_en": solicitud.creado_en.isoformat(),
        "atendida_en": solicitud.atendida_en.isoformat() if solicitud.atendida_en else None,
    }


@superadministracion_bp.get("/contratos-empresariales")
@login_required
@requerir_permiso("superadmin.suscripciones")
def contratos_empresariales():
    solicitudes = ServicioSuperAdministracion(current_user).listar_solicitudes_empresariales(
        estado=request.args.get("estado")
    )
    return jsonify({"solicitudes": [_contrato_empresarial(s) for s in solicitudes]})


@superadministracion_bp.patch("/contratos-empresariales/<int:solicitud_id>")
@login_required
@requerir_permiso("superadmin.suscripciones")
def actualizar_contrato_empresarial(solicitud_id):
    try:
        datos = request.get_json(silent=True) or {}
        solicitud = ServicioSuperAdministracion(current_user).actualizar_solicitud_empresarial(
            solicitud_id,
            estado=datos.get("estado"),
            observacion=datos.get("observacion"),
        )
        return jsonify(_contrato_empresarial(solicitud))
    except ErrorSuperAdministracion as exc:
        return _error(exc)


@superadministracion_bp.patch("/suscripciones/<int:suscripcion_id>")
@login_required
@requerir_permiso("superadmin.suscripciones")
def editar_suscripcion(suscripcion_id):
    try:
        datos = request.get_json(silent=True) or {}
        suscripcion = ServicioSuperAdministracion(current_user).editar_suscripcion(
            suscripcion_id, **datos
        )
        return jsonify(
            {
                "id": suscripcion.id,
                "empresa_id": suscripcion.empresa_id,
                "plan_id": suscripcion.plan_id,
                "estado": suscripcion.estado,
                "ciclo": suscripcion.ciclo,
                "fecha_inicio": suscripcion.fecha_inicio.isoformat(),
                "fecha_fin": suscripcion.fecha_fin.isoformat() if suscripcion.fecha_fin else None,
                "renovacion_automatica": suscripcion.renovacion_automatica,
                "cancelar_al_fin_periodo": suscripcion.cancelar_al_fin_periodo,
            }
        )
    except (ErrorSuperAdministracion, TypeError) as exc:
        if isinstance(exc, TypeError):
            exc = ErrorSuperAdministracion("Campos de suscripción no admitidos")
        return _error(exc)


@superadministracion_bp.get("/pagos")
@login_required
@requerir_permiso("superadmin.pagos")
def pagos():
    datos = ServicioSuperAdministracion(current_user).listar_pagos(
        empresa_id=request.args.get("empresa_id", type=int),
        estado=request.args.get("estado"),
        proveedor=request.args.get("proveedor"),
    )
    return jsonify(
        {
            "pagos": [
                {
                    "id": p.id,
                    "empresa_id": p.empresa_id,
                    "proveedor": p.proveedor,
                    "referencia_externa": p.referencia_externa,
                    "estado": p.estado,
                    "monto": str(p.monto),
                    "moneda": p.moneda,
                    "fecha": p.creado_en.isoformat(),
                    "fecha_confirmacion": (
                        p.fecha_confirmacion.isoformat() if p.fecha_confirmacion else None
                    ),
                }
                for p in datos
            ]
        }
    )


@superadministracion_bp.get("/documentos-facturacion")
@login_required
@requerir_permiso("superadmin.pagos")
def documentos_facturacion():
    try:
        datos = ServicioSuperAdministracion(current_user).listar_documentos_facturacion(
            empresa_id=request.args.get("empresa_id", type=int),
            estado=request.args.get("estado"),
        )
        return jsonify(
            {
                "documentos": [
                    {
                        "id": documento.id,
                        "empresa_id": documento.empresa_id,
                        "pago_id": documento.pago_id,
                        "numero": documento.numero,
                        "tipo": documento.tipo,
                        "estado": documento.estado,
                        "moneda": documento.moneda,
                        "total": str(documento.total),
                        "emitido_en": documento.emitido_en.isoformat(),
                    }
                    for documento in datos
                ]
            }
        )
    except ErrorSuperAdministracion as exc:
        return _error(exc)


@superadministracion_bp.get("/auditoria")
@login_required
@requerir_permiso("superadmin.auditoria")
def auditoria():
    datos = ServicioSuperAdministracion(current_user).listar_auditoria(
        empresa_id=request.args.get("empresa_id", type=int),
        accion=request.args.get("accion"),
        limite=request.args.get("limite", 200),
    )
    return jsonify(
        {
            "auditoria": [
                {
                    "id": a.id,
                    "empresa_id": a.empresa_id,
                    "usuario_id": a.usuario_id,
                    "accion": a.accion,
                    "modulo": a.modulo,
                    "entidad_tipo": a.entidad_tipo,
                    "entidad_id": a.entidad_id,
                    "fecha": a.fecha.isoformat(),
                }
                for a in datos
            ]
        }
    )


def _usuario(usuario):
    empresa = usuario.empresa
    ubicacion = None
    if (
        usuario.ubicacion_consentida
        and usuario.ultima_latitud is not None
        and usuario.ultima_longitud is not None
    ):
        ubicacion = {
            "latitud": float(usuario.ultima_latitud),
            "longitud": float(usuario.ultima_longitud),
            "precision_m": (
                float(usuario.ultima_precision_m)
                if usuario.ultima_precision_m is not None
                else None
            ),
            "actualizada_en": usuario.ubicacion_actualizada_en.isoformat(),
        }
    return {
        "id": usuario.id,
        "empresa_id": usuario.empresa_id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "nombre_completo": f"{usuario.nombre} {usuario.apellido or ''}".strip(),
        "identificacion_fiscal": usuario.identificacion_fiscal,
        "telefono": usuario.telefono,
        "email": usuario.email,
        "rol": usuario.rol,
        "activo": usuario.activo,
        "bloqueado": usuario.esta_bloqueado(),
        "email_verificado": usuario.email_verificado,
        "ultimo_acceso": usuario.ultimo_acceso.isoformat() if usuario.ultimo_acceso else None,
        "creado_en": usuario.creado_en.isoformat(),
        "ubicacion": ubicacion,
        "empresa": _empresa(empresa) if empresa else None,
    }


@superadministracion_bp.get("/usuarios")
@login_required
@requerir_permiso("superadmin.usuarios")
def usuarios():
    try:
        datos = ServicioSuperAdministracion(current_user).listar_usuarios(
            empresa_id=request.args.get("empresa_id", type=int),
            rol=request.args.get("rol"),
            estado=request.args.get("estado"),
            buscar=request.args.get("buscar"),
        )
        return jsonify({"usuarios": [_usuario(usuario) for usuario in datos]})
    except ErrorSuperAdministracion as exc:
        return _error(exc)


@superadministracion_bp.patch("/usuarios/<int:usuario_id>/estado")
@login_required
@requerir_permiso("superadmin.usuarios")
def cambiar_estado_usuario(usuario_id):
    try:
        usuario = ServicioSuperAdministracion(current_user).cambiar_estado_usuario(
            usuario_id, activo=(request.get_json(silent=True) or {}).get("activo")
        )
        return jsonify(_usuario(usuario))
    except ErrorSuperAdministracion as exc:
        return _error(exc)


@superadministracion_bp.post("/usuarios/<int:usuario_id>/desbloquear")
@login_required
@requerir_permiso("superadmin.usuarios")
def desbloquear_usuario(usuario_id):
    try:
        usuario = ServicioSuperAdministracion(current_user).desbloquear_usuario(usuario_id)
        return jsonify(_usuario(usuario))
    except ErrorSuperAdministracion as exc:
        return _error(exc)


@superadministracion_bp.get("/sistema")
@login_required
@requerir_permiso("superadmin.sistema")
def sistema():
    return jsonify(ServicioSuperAdministracion(current_user).estado_sistema())


@superadministracion_bp.get("/seguridad")
@login_required
@requerir_permiso("superadmin.sistema")
def seguridad():
    return jsonify(ServicioSuperAdministracion(current_user).resumen_seguridad())
