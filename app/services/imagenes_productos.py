"""Gestión segura de imágenes públicas asociadas a productos."""

from urllib.parse import urlparse

from flask import current_app

from sqlalchemy.exc import IntegrityError

from ..models import Producto, ProductoImagen, db
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria


class ErrorImagenProducto(ValueError):
    codigo = "imagen_producto_invalida"


class ServicioImagenesProductos:
    MAXIMO = 8

    def __init__(self, actor):
        self.actor = actor
        if not actor.empresa_id or actor.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def listar(self, producto_id):
        self._exigir("productos.ver")
        producto = self._producto(producto_id)
        return producto, list(
            db.session.scalars(
                db.select(ProductoImagen)
                .where(
                    ProductoImagen.empresa_id == self.actor.empresa_id,
                    ProductoImagen.producto_id == producto.id,
                )
                .order_by(ProductoImagen.orden, ProductoImagen.id)
            )
        )

    def agregar(self, producto_id, *, url, es_principal=False):
        self._exigir("productos.editar")
        producto, imagenes = self.listar(producto_id)
        if len(imagenes) >= self.MAXIMO:
            raise ErrorImagenProducto(f"Cada producto admite hasta {self.MAXIMO} imágenes")
        url = self._url(url)
        if any(imagen.url == url for imagen in imagenes):
            raise ErrorImagenProducto("La imagen ya está asociada al producto")
        try:
            principal = bool(es_principal) or not imagenes
            if principal:
                for imagen in imagenes:
                    imagen.es_principal = False
            imagen = ProductoImagen(
                empresa_id=self.actor.empresa_id,
                producto_id=producto.id,
                url=url,
                orden=(max((i.orden for i in imagenes), default=-1) + 1),
                es_principal=principal,
            )
            db.session.add(imagen)
            db.session.flush()
            self._auditar(imagen, "agregada")
            db.session.commit()
            return imagen
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorImagenProducto("No fue posible ordenar la imagen") from exc

    def establecer_principal(self, producto_id, imagen_id):
        self._exigir("productos.editar")
        _, imagenes = self.listar(producto_id)
        objetivo = next((i for i in imagenes if i.id == imagen_id), None)
        if not objetivo:
            raise PermissionError("Imagen no autorizada")
        for imagen in imagenes:
            imagen.es_principal = imagen.id == objetivo.id
        self._auditar(objetivo, "principal")
        db.session.commit()
        return objetivo

    def reordenar(self, producto_id, ids):
        self._exigir("productos.editar")
        _, imagenes = self.listar(producto_id)
        try:
            ids = [int(valor) for valor in ids]
        except (TypeError, ValueError) as exc:
            raise ErrorImagenProducto("El orden no es válido") from exc
        if set(ids) != {imagen.id for imagen in imagenes} or len(ids) != len(imagenes):
            raise ErrorImagenProducto("Debe incluir todas las imágenes una sola vez")
        # Usa valores temporales para no violar la restricción única durante el cambio.
        for indice, imagen in enumerate(imagenes):
            imagen.orden = -(indice + 1)
        db.session.flush()
        por_id = {imagen.id: imagen for imagen in imagenes}
        for orden, imagen_id in enumerate(ids):
            por_id[imagen_id].orden = orden
        db.session.commit()
        return [por_id[imagen_id] for imagen_id in ids]

    def eliminar(self, producto_id, imagen_id):
        self._exigir("productos.editar")
        _, imagenes = self.listar(producto_id)
        imagen = next((i for i in imagenes if i.id == imagen_id), None)
        if not imagen:
            raise PermissionError("Imagen no autorizada")
        era_principal = imagen.es_principal
        self._auditar(imagen, "eliminada")
        db.session.delete(imagen)
        restantes = [i for i in imagenes if i.id != imagen.id]
        for orden, restante in enumerate(restantes):
            restante.orden = orden
        if era_principal and restantes:
            restantes[0].es_principal = True
        db.session.commit()

    def _producto(self, producto_id):
        producto = db.session.scalar(
            db.select(Producto).where(
                Producto.id == producto_id,
                Producto.empresa_id == self.actor.empresa_id,
                Producto.eliminado.is_(False),
            )
        )
        if not producto:
            raise PermissionError("Producto no autorizado")
        return producto

    @staticmethod
    def _url(valor):
        valor = (valor or "").strip()
        partes = urlparse(valor)
        if (
            partes.scheme != "https"
            or not partes.netloc
            or partes.username
            or partes.password
            or not partes.path.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
            or any(caracter in valor for caracter in ('"', "'", "<", ">", "\n", "\r"))
        ):
            raise ErrorImagenProducto("Debe indicar una URL HTTPS de imagen válida")
        permitidos = {
            str(host).lower() for host in current_app.config.get("IMAGE_ALLOWED_HOSTS", [])
        }
        host = (partes.hostname or "").lower()
        if not permitidos or not any(
            host == permitido or host.endswith("." + permitido) for permitido in permitidos
        ):
            raise ErrorImagenProducto("El alojamiento de la imagen no está autorizado")
        return valor

    def _auditar(self, imagen, accion):
        registrar_auditoria(
            accion=f"producto.imagen_{accion}",
            modulo="productos",
            usuario_id=self.actor.id,
            empresa_id=self.actor.empresa_id,
            entidad_tipo="ProductoImagen",
            entidad_id=imagen.id,
            datos_nuevos={"producto_id": imagen.producto_id, "url": imagen.url},
        )

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.actor, permiso, empresa_id=self.actor.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)
