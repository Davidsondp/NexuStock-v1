import base64
from io import BytesIO

import qrcode
from qrcode.image.svg import SvgPathImage
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ...permisos import requerir_permiso
from ...services.productos import ErrorProducto, ServicioProductos
from ...services.imagenes_productos import ErrorImagenProducto, ServicioImagenesProductos

from ...services.unidades_medida import (
    ErrorUnidadMedida,
    ServicioUnidadesMedida,
)

productos_bp = Blueprint("productos", __name__, url_prefix="/api/productos")


def _serializar_presentacion(
    presentacion,
):
    return {
        "id": presentacion["id"],
        "codigo": presentacion["codigo"],
        "nombre": presentacion["nombre"],
        "abreviatura": presentacion["abreviatura"],
        "factor_base": format(
            presentacion["factor_base"],
            ".3f",
        ),
        "es_base": presentacion["es_base"],
        "activa": presentacion["activa"],
    }


def _serializar(producto):
    return {
        "id": producto.id,
        "codigo": producto.codigo,
        "codigo_barras": producto.codigo_barras,
        "nombre": producto.nombre,
        "descripcion": producto.descripcion,
        "categoria": producto.categoria,
        "subcategoria": producto.subcategoria,
        "marca": producto.marca,
        "unidad_medida": producto.unidad_medida,
        "unidades_por_caja": str(producto.unidades_por_caja),
        "costo_referencia": str(producto.costo_referencia),
        "precio_venta": str(producto.precio_venta),
        "incluye_iva": producto.incluye_iva,
        "tasa_impuesto": str(producto.tasa_impuesto),
        "stock_minimo": str(producto.stock_minimo),
        "punto_reorden": str(producto.punto_reorden),
        "stock_maximo": (str(producto.stock_maximo) if producto.stock_maximo is not None else None),
        "requiere_serial": producto.requiere_serial,
        "controla_lotes": producto.controla_lotes,
        "controla_vencimiento": producto.controla_vencimiento,
        "campos_personalizados": dict(producto.campos_personalizados or {}),
        "activo": producto.activo,
        "proveedor_principal_id": producto.proveedor_principal_id,
        "imagen_principal": next(
            (imagen.url for imagen in producto.imagenes if imagen.es_principal), None
        ),
        "imagenes": [
            {"id": i.id, "url": i.url, "orden": i.orden, "es_principal": i.es_principal}
            for i in sorted(producto.imagenes, key=lambda imagen: imagen.orden)
        ],
    }


@productos_bp.get("")
@login_required
@requerir_permiso("productos.ver")
def listar():
    valor_inactivos = request.args.get("incluir_inactivos", "").strip().lower()

    incluir_inactivos = valor_inactivos in {
        "1",
        "true",
        "si",
        "yes",
    }

    productos = ServicioProductos(current_user).listar(
        busqueda=request.args.get("buscar"),
        incluir_inactivos=incluir_inactivos,
    )

    return jsonify({"productos": [_serializar(producto) for producto in productos]})


@productos_bp.post("")
@login_required
@requerir_permiso("productos.crear")
def crear():
    try:
        producto = ServicioProductos(current_user).crear(**(request.get_json(silent=True) or {}))
        return jsonify(_serializar(producto)), 201
    except ErrorProducto as exc:
        return jsonify({"codigo": "producto_invalido", "mensaje": str(exc)}), 400


@productos_bp.patch("/<int:producto_id>")
@login_required
@requerir_permiso("productos.editar")
def editar(producto_id):
    try:
        producto = ServicioProductos(current_user).editar(
            producto_id, **(request.get_json(silent=True) or {})
        )
        return jsonify(_serializar(producto))
    except ErrorProducto as exc:
        return jsonify({"codigo": "producto_invalido", "mensaje": str(exc)}), 400


@productos_bp.get("/<int:producto_id>/presentaciones")
@login_required
@requerir_permiso("productos.ver")
def listar_presentaciones(producto_id):
    servicio = ServicioUnidadesMedida(current_user)
    presentaciones = servicio.listar(producto_id)

    return jsonify(
        {
            "producto_id": producto_id,
            "unidad_base": _serializar_presentacion(presentaciones[0]),
            "presentaciones": [
                _serializar_presentacion(presentacion) for presentacion in presentaciones[1:]
            ],
        }
    )


@productos_bp.post("/<int:producto_id>/presentaciones")
@login_required
@requerir_permiso("productos.editar")
def crear_presentacion(producto_id):
    datos = request.get_json(silent=True) or {}

    try:
        servicio = ServicioUnidadesMedida(current_user)
        presentacion = servicio.crear(
            producto_id=producto_id,
            codigo=datos.get("codigo"),
            nombre=datos.get("nombre"),
            abreviatura=datos.get("abreviatura"),
            factor_base=datos.get("factor_base"),
        )

        return jsonify(_serializar_presentacion(servicio.serializar(presentacion))), 201
    except ErrorUnidadMedida as exc:
        return (
            jsonify(
                {
                    "codigo": "presentacion_invalida",
                    "mensaje": str(exc),
                }
            ),
            400,
        )


@productos_bp.patch("/<int:producto_id>/presentaciones/" "<int:presentacion_id>")
@login_required
@requerir_permiso("productos.editar")
def editar_presentacion(
    producto_id,
    presentacion_id,
):
    datos = request.get_json(silent=True) or {}

    try:
        servicio = ServicioUnidadesMedida(current_user)
        presentacion = servicio.editar(
            producto_id=producto_id,
            presentacion_id=presentacion_id,
            codigo=datos.get("codigo"),
            nombre=datos.get("nombre"),
            abreviatura=datos.get("abreviatura"),
            factor_base=datos.get("factor_base"),
        )

        return jsonify(_serializar_presentacion(servicio.serializar(presentacion)))
    except ErrorUnidadMedida as exc:
        return (
            jsonify(
                {
                    "codigo": "presentacion_invalida",
                    "mensaje": str(exc),
                }
            ),
            400,
        )


@productos_bp.post("/<int:producto_id>/presentaciones/" "<int:presentacion_id>/desactivar")
@login_required
@requerir_permiso("productos.editar")
def desactivar_presentacion(
    producto_id,
    presentacion_id,
):
    try:
        servicio = ServicioUnidadesMedida(current_user)
        presentacion = servicio.desactivar(
            producto_id=producto_id,
            presentacion_id=presentacion_id,
        )

        return jsonify(_serializar_presentacion(servicio.serializar(presentacion)))
    except ErrorUnidadMedida as exc:
        return (
            jsonify(
                {
                    "codigo": "presentacion_invalida",
                    "mensaje": str(exc),
                }
            ),
            400,
        )


@productos_bp.post("/<int:producto_id>/desactivar")
@login_required
@requerir_permiso("productos.eliminar")
def desactivar(producto_id):
    producto = ServicioProductos(current_user).desactivar(producto_id)

    return jsonify(_serializar(producto))


@productos_bp.post("/<int:producto_id>/reactivar")
@login_required
@requerir_permiso("productos.eliminar")
def reactivar(producto_id):
    producto = ServicioProductos(current_user).reactivar(producto_id)

    return jsonify(_serializar(producto))


@productos_bp.delete("/<int:producto_id>")
@login_required
@requerir_permiso("productos.eliminar")
def eliminar(producto_id):
    try:
        ServicioProductos(current_user).eliminar_logicamente(producto_id)
        return "", 204
    except ErrorProducto as exc:
        return jsonify({"codigo": "producto_con_historial", "mensaje": str(exc)}), 409


@productos_bp.get("/<int:producto_id>/etiqueta")
@login_required
@requerir_permiso("productos.ver")
def etiqueta_imprimible(producto_id):
    """Etiqueta autocontenida; el código se renderiza en el cliente para imprimir."""
    producto = ServicioProductos(current_user).obtener(producto_id)
    codigo = producto.codigo_barras or producto.codigo
    imagen = qrcode.make(codigo, image_factory=SvgPathImage)
    salida = BytesIO()
    imagen.save(salida)
    qr = "data:image/svg+xml;base64," + base64.b64encode(salida.getvalue()).decode("ascii")
    return jsonify(
        {
            "producto": {
                "id": producto.id,
                "codigo": producto.codigo,
                "codigo_barras": codigo,
                "nombre": producto.nombre,
                "precio_venta": str(producto.precio_venta),
                "qr": qr,
            },
            "formato": "etiqueta_62x30_mm",
        }
    )


def _imagen(imagen):
    return {
        "id": imagen.id,
        "url": imagen.url,
        "orden": imagen.orden,
        "es_principal": imagen.es_principal,
    }


@productos_bp.get("/<int:producto_id>/imagenes")
@login_required
@requerir_permiso("productos.ver")
def listar_imagenes(producto_id):
    producto, imagenes = ServicioImagenesProductos(current_user).listar(producto_id)
    return jsonify(
        {
            "producto": {"id": producto.id, "nombre": producto.nombre},
            "imagenes": [_imagen(i) for i in imagenes],
        }
    )


@productos_bp.post("/<int:producto_id>/imagenes")
@login_required
@requerir_permiso("productos.editar")
def agregar_imagen(producto_id):
    try:
        imagen = ServicioImagenesProductos(current_user).agregar(
            producto_id, **(request.get_json(silent=True) or {})
        )
        return jsonify(_imagen(imagen)), 201
    except (ErrorImagenProducto, TypeError) as exc:
        return jsonify({"codigo": "imagen_producto_invalida", "mensaje": str(exc)}), 400


@productos_bp.post("/<int:producto_id>/imagenes/<int:imagen_id>/principal")
@login_required
@requerir_permiso("productos.editar")
def imagen_principal(producto_id, imagen_id):
    imagen = ServicioImagenesProductos(current_user).establecer_principal(producto_id, imagen_id)
    return jsonify(_imagen(imagen))


@productos_bp.put("/<int:producto_id>/imagenes/orden")
@login_required
@requerir_permiso("productos.editar")
def ordenar_imagenes(producto_id):
    try:
        imagenes = ServicioImagenesProductos(current_user).reordenar(
            producto_id, (request.get_json(silent=True) or {}).get("ids") or []
        )
        return jsonify({"imagenes": [_imagen(i) for i in imagenes]})
    except ErrorImagenProducto as exc:
        return jsonify({"codigo": exc.codigo, "mensaje": str(exc)}), 400


@productos_bp.delete("/<int:producto_id>/imagenes/<int:imagen_id>")
@login_required
@requerir_permiso("productos.editar")
def eliminar_imagen(producto_id, imagen_id):
    ServicioImagenesProductos(current_user).eliminar(producto_id, imagen_id)
    return "", 204
