from flask import Blueprint, jsonify, request, send_file
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.reportes import ErrorReporte, ServicioReportes, construir_periodo
from ...services.exportaciones import ErrorExportacion, ServicioExportaciones

reportes_bp = Blueprint("reportes", __name__, url_prefix="/api/reportes")


def _error(exc):
    return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400


@reportes_bp.get("/productos")
@login_required
@requerir_permiso("reportes.ver")
def productos():
    datos = ServicioReportes(current_user).productos()
    return jsonify(
        {
            "productos": [
                {
                    "id": p.id,
                    "codigo": p.codigo,
                    "nombre": p.nombre,
                    "categoria": p.categoria,
                    "precio_venta": str(p.precio_venta),
                }
                for p in datos
            ]
        }
    )


@reportes_bp.get("/stock")
@login_required
@requerir_permiso("reportes.ver")
def stock():
    filas = ServicioReportes(current_user).stock(bodega_id=request.args.get("bodega_id", type=int))
    return jsonify(
        {
            "stock": [
                {
                    "producto_id": p.id,
                    "producto": p.nombre,
                    "bodega_id": b.id,
                    "bodega": b.nombre,
                    "cantidad": str(i.cantidad),
                    "reservada": str(i.cantidad_reservada),
                    "disponible": str(i.cantidad_disponible),
                    "costo_promedio": str(i.costo_promedio),
                    "valor": str(
                        (i.cantidad * i.costo_promedio).quantize(
                            __import__("decimal").Decimal("0.01")
                        )
                    ),
                }
                for i, p, b in filas
            ]
        }
    )


@reportes_bp.get("/dinero-dormido")
@login_required
@requerir_permiso("reportes.ver")
def dinero_dormido():
    return jsonify(
        ServicioReportes(current_user).dinero_dormido(
            bodega_id=request.args.get("bodega_id", type=int)
        )
    )


@reportes_bp.get("/movimientos")
@login_required
@requerir_permiso("reportes.ver")
def movimientos():
    try:
        periodo = construir_periodo(request.args.get("desde"), request.args.get("hasta"))
        datos = ServicioReportes(current_user).movimientos(
            periodo,
            bodega_id=request.args.get("bodega_id", type=int),
            limite=request.args.get("limite", 500),
        )
        return jsonify(
            {
                "movimientos": [
                    {
                        "id": m.id,
                        "fecha": m.fecha.isoformat(),
                        "tipo": m.tipo,
                        "producto_id": m.producto_id,
                        "bodega_id": m.bodega_id,
                        "cantidad": str(m.cantidad),
                        "stock_nuevo": str(m.stock_nuevo),
                        "motivo": m.motivo,
                    }
                    for m in datos
                ]
            }
        )
    except ErrorReporte as exc:
        return _error(exc)


@reportes_bp.get("/analitica")
@login_required
@requerir_permiso("analitica.ver")
def analitica():
    try:
        periodo = construir_periodo(request.args.get("desde"), request.args.get("hasta"))
        return jsonify(
            ServicioReportes(current_user).analitica(
                periodo,
                bodega_id=request.args.get("bodega_id", type=int),
                limite=request.args.get("limite", 10),
            )
        )
    except ErrorReporte as exc:
        return _error(exc)


@reportes_bp.get("/resumen-ejecutivo")
@login_required
@requerir_permiso("dashboard.ejecutivo")
def resumen_ejecutivo():
    try:
        periodo = construir_periodo(request.args.get("desde"), request.args.get("hasta"))
        return jsonify(
            ServicioReportes(current_user).resumen_ejecutivo(
                periodo, bodega_id=request.args.get("bodega_id", type=int)
            )
        )
    except ErrorReporte as exc:
        return _error(exc)


@reportes_bp.get("/exportar/<reporte>.<formato>")
@login_required
@requerir_permiso("reportes.exportar")
def exportar(reporte, formato):
    try:
        periodo = construir_periodo(request.args.get("desde"), request.args.get("hasta"))
        contenido, nombre, mime = ServicioExportaciones(current_user).exportar(
            reporte, formato, periodo=periodo, bodega_id=request.args.get("bodega_id", type=int)
        )
        return send_file(
            contenido,
            mimetype=mime,
            as_attachment=True,
            download_name=nombre,
            max_age=0,
            conditional=False,
        )
    except (ErrorReporte, ErrorExportacion) as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400
