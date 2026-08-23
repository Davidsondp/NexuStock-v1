from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from ...extensions import csrf
from ...permisos import requerir_permiso
from ...services.suite_comercial import (
    ErrorSuiteComercial,
    ClienteDTEHttp,
    ServicioDTE,
    ServicioGrupoEmpresarial,
    ServicioIntegraciones,
    ServicioPOS,
    ServicioWMS,
)

suite_comercial_bp = Blueprint("suite_comercial", __name__, url_prefix="/api/comercial")
integraciones_webhook_bp = Blueprint(
    "integraciones_webhook", __name__, url_prefix="/webhooks/integraciones"
)


def _error(exc, estado=400):
    return (
        jsonify({"codigo": getattr(exc, "codigo", "operacion_invalida"), "mensaje": str(exc)}),
        estado,
    )


def _turno(turno):
    return {
        "id": turno.id,
        "caja_id": turno.caja_id,
        "estado": turno.estado,
        "monto_apertura": str(turno.monto_apertura),
        "monto_cierre_calculado": (
            str(turno.monto_cierre_calculado) if turno.monto_cierre_calculado is not None else None
        ),
        "diferencia": str(turno.diferencia) if turno.diferencia is not None else None,
    }


def _wms(orden):
    return {
        "id": orden.id,
        "numero": orden.numero,
        "venta_id": orden.venta_id,
        "estado": orden.estado,
        "transportista": orden.transportista,
        "seguimiento": orden.seguimiento,
    }


@suite_comercial_bp.get("/multiempresa/resumen")
@login_required
@requerir_permiso("multiempresa.ver")
def resumen_multiempresa():
    return jsonify(ServicioGrupoEmpresarial(current_user).resumen())


@suite_comercial_bp.post("/pos/turnos")
@login_required
@requerir_permiso("pos.operar")
def abrir_turno():
    try:
        datos = request.get_json(silent=True) or {}
        return (
            jsonify(
                _turno(
                    ServicioPOS(current_user).abrir(
                        datos.get("caja_id"), datos.get("monto_apertura", 0)
                    )
                )
            ),
            201,
        )
    except ErrorSuiteComercial as exc:
        return _error(exc)


@suite_comercial_bp.post("/pos/turnos/<int:turno_id>/ventas")
@login_required
@requerir_permiso("pos.operar")
def venta_pos(turno_id):
    try:
        datos = request.get_json(silent=True) or {}
        venta, creada = ServicioPOS(current_user).vender(
            turno_id,
            numero=datos.get("numero"),
            bodega_id=datos.get("bodega_id"),
            items=datos.get("items"),
            pagos=datos.get("pagos"),
            clave_idempotencia=request.headers.get("Idempotency-Key") or "",
            cliente_id=datos.get("cliente_id"),
        )
        return jsonify(
            {
                "venta_id": venta.id,
                "numero": venta.numero,
                "estado": venta.estado,
                "total": str(venta.total),
                "creada": creada,
            }
        ), (201 if creada else 200)
    except (ErrorSuiteComercial, TypeError, ValueError) as exc:
        return _error(exc)


@suite_comercial_bp.post("/pos/turnos/<int:turno_id>/cerrar")
@login_required
@requerir_permiso("pos.operar")
def cerrar_turno(turno_id):
    try:
        return jsonify(
            _turno(
                ServicioPOS(current_user).cerrar(
                    turno_id, (request.get_json(silent=True) or {}).get("monto_declarado")
                )
            )
        )
    except ErrorSuiteComercial as exc:
        return _error(exc)


@suite_comercial_bp.post("/wms/ordenes")
@login_required
@requerir_permiso("wms.operar")
def crear_wms():
    try:
        datos = request.get_json(silent=True) or {}
        return (
            jsonify(
                _wms(
                    ServicioWMS(current_user).crear(
                        datos.get("venta_id"), datos.get("numero"), datos.get("asignada_a_id")
                    )
                )
            ),
            201,
        )
    except ErrorSuiteComercial as exc:
        return _error(exc)


@suite_comercial_bp.post("/wms/ordenes/<int:orden_id>/avanzar")
@login_required
@requerir_permiso("wms.operar")
def avanzar_wms(orden_id):
    try:
        datos = request.get_json(silent=True) or {}
        return jsonify(
            _wms(
                ServicioWMS(current_user).avanzar(
                    orden_id,
                    transportista=datos.get("transportista"),
                    seguimiento=datos.get("seguimiento"),
                )
            )
        )
    except ErrorSuiteComercial as exc:
        return _error(exc)


@suite_comercial_bp.post("/wms/ordenes/<int:orden_id>/escanear")
@login_required
@requerir_permiso("wms.operar")
def escanear_wms(orden_id):
    try:
        datos = request.get_json(silent=True) or {}
        orden = ServicioWMS(current_user).escanear(
            orden_id,
            etapa=datos.get("etapa"),
            codigo_producto=datos.get("codigo_producto"),
            cantidad=datos.get("cantidad"),
        )
        return jsonify(_wms(orden))
    except ErrorSuiteComercial as exc:
        return _error(exc)


@suite_comercial_bp.post("/dte")
@login_required
@requerir_permiso("dte.emitir")
def emitir_dte():
    try:
        datos = request.get_json(silent=True) or {}
        fabrica = current_app.config.get("DTE_CLIENT_FACTORY")
        cliente = (
            fabrica()
            if callable(fabrica)
            else ClienteDTEHttp(
                current_app.config.get("DTE_PROVIDER_URL"),
                current_app.config.get("DTE_API_KEY"),
            )
        )
        documento, creado = ServicioDTE(current_user).emitir(
            datos.get("venta_id"),
            tipo=datos.get("tipo"),
            proveedor=datos.get("proveedor") or "certificado",
            clave_idempotencia=request.headers.get("Idempotency-Key") or "",
            cliente=cliente,
            documento_referencia=datos.get("documento_referencia_id"),
        )
        return jsonify(
            {
                "id": documento.id,
                "venta_id": documento.venta_id,
                "tipo": documento.tipo,
                "folio": documento.folio,
                "estado": documento.estado,
                "creado": creado,
            }
        ), (201 if creado else 200)
    except (ErrorSuiteComercial, KeyError, TypeError, ValueError) as exc:
        return _error(exc, 503 if "Configura" in str(exc) else 400)


@suite_comercial_bp.post("/integraciones")
@login_required
@requerir_permiso("integraciones.gestionar")
def crear_integracion():
    try:
        datos = request.get_json(silent=True) or {}
        integracion = ServicioIntegraciones(current_user).crear(
            datos.get("proveedor"), datos.get("secreto")
        )
        return (
            jsonify(
                {
                    "id": integracion.id,
                    "proveedor": integracion.proveedor,
                    "estado": integracion.estado,
                }
            ),
            201,
        )
    except ErrorSuiteComercial as exc:
        return _error(exc)


@integraciones_webhook_bp.post("/<int:integracion_id>")
@csrf.exempt
def recibir_integracion(integracion_id):
    try:
        cuerpo = request.get_data(cache=True)
        datos = request.get_json(silent=True) or {}
        evento, procesado = ServicioIntegraciones.recibir(
            integracion_id,
            request.headers.get("X-Event-ID") or "",
            request.headers.get("X-Event-Type") or "evento",
            datos,
            request.headers.get("X-Webhook-Signature") or "",
            request.headers.get("X-Webhook-Timestamp") or "",
            cuerpo,
        )
        return jsonify({"evento_id": evento.id, "estado": evento.estado, "procesado": procesado})
    except PermissionError as exc:
        return _error(exc, 401)
    except ErrorSuiteComercial as exc:
        return _error(exc)
