"""Unidades base y presentaciones comerciales."""

from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
)

from sqlalchemy.exc import IntegrityError

from ..models import (
    PresentacionProducto,
    Producto,
    db,
)
from ..permisos import evaluar_permiso

PRECISION_CANTIDAD = Decimal("0.001")


UNIDADES_BASE = {
    "unidad": {
        "nombre": "Unidad",
        "abreviatura": "un",
    },
    "kilogramo": {
        "nombre": "Kilogramo",
        "abreviatura": "kg",
    },
    "gramo": {
        "nombre": "Gramo",
        "abreviatura": "g",
    },
    "litro": {
        "nombre": "Litro",
        "abreviatura": "L",
    },
    "mililitro": {
        "nombre": "Mililitro",
        "abreviatura": "mL",
    },
    "metro": {
        "nombre": "Metro",
        "abreviatura": "m",
    },
    "centimetro": {
        "nombre": "Centímetro",
        "abreviatura": "cm",
    },
    "pieza": {
        "nombre": "Pieza",
        "abreviatura": "pz",
    },
}


UNIDADES_BASE.update(
    {
        "botella": {
            "nombre": "Botella",
            "abreviatura": "bot",
        },
        "lata": {
            "nombre": "Lata",
            "abreviatura": "lata",
        },
        "comprimido": {
            "nombre": "Comprimido",
            "abreviatura": "comp",
        },
        "capsula": {
            "nombre": "Cápsula",
            "abreviatura": "cap",
        },
        "dosis": {
            "nombre": "Dosis",
            "abreviatura": "dosis",
        },
        "rollo": {
            "nombre": "Rollo",
            "abreviatura": "rollo",
        },
        "saco": {
            "nombre": "Saco",
            "abreviatura": "saco",
        },
    }
)


UNIDADES_POR_RUBRO = {
    "general": (
        "unidad",
        "pieza",
        "kilogramo",
        "gramo",
        "litro",
    ),
    "tienda": (
        "unidad",
        "pieza",
        "kilogramo",
        "gramo",
        "litro",
    ),
    "almacen": (
        "unidad",
        "kilogramo",
        "gramo",
        "litro",
        "mililitro",
        "saco",
    ),
    "minimarket": (
        "unidad",
        "kilogramo",
        "gramo",
        "litro",
        "mililitro",
        "botella",
        "lata",
    ),
    "botilleria": (
        "unidad",
        "botella",
        "lata",
        "litro",
        "mililitro",
    ),
    "ferreteria": (
        "unidad",
        "pieza",
        "metro",
        "centimetro",
        "kilogramo",
        "rollo",
    ),
    "farmacia": (
        "unidad",
        "comprimido",
        "capsula",
        "dosis",
        "gramo",
        "mililitro",
    ),
}


def unidades_sugeridas(
    rubro,
) -> list[dict]:
    codigo_rubro = str(rubro or "general").strip().lower()
    codigos = UNIDADES_POR_RUBRO.get(
        codigo_rubro,
        UNIDADES_POR_RUBRO["general"],
    )

    return [
        {
            "codigo": codigo,
            **UNIDADES_BASE[codigo],
        }
        for codigo in codigos
    ]


class ErrorUnidadMedida(ValueError):
    """La unidad o presentación no es válida."""


class ServicioUnidadesMedida:
    def __init__(self, usuario):
        self.usuario = usuario

    def listar(
        self,
        producto_id: int,
        *,
        incluir_inactivas: bool = False,
    ) -> list[dict]:
        self._exigir("productos.ver")
        producto = self._obtener_producto(producto_id)

        consulta = db.select(PresentacionProducto).where(
            PresentacionProducto.empresa_id == self.usuario.empresa_id,
            PresentacionProducto.producto_id == producto.id,
        )

        if not incluir_inactivas:
            consulta = consulta.where(PresentacionProducto.activa.is_(True))

        presentaciones = list(
            db.session.scalars(
                consulta.order_by(
                    PresentacionProducto.nombre,
                    PresentacionProducto.id,
                )
            )
        )

        return [
            self._unidad_base(producto),
            *[self.serializar(presentacion) for presentacion in presentaciones],
        ]

    def crear(
        self,
        *,
        producto_id: int,
        codigo,
        nombre,
        abreviatura,
        factor_base,
    ) -> PresentacionProducto:
        self._exigir("productos.editar")
        producto = self._obtener_producto(producto_id)

        codigo_normalizado = str(codigo or "").strip().upper()
        nombre_normalizado = str(nombre or "").strip()
        abreviatura_normalizada = str(abreviatura or "").strip()

        if not codigo_normalizado or not nombre_normalizado or not abreviatura_normalizada:
            raise ErrorUnidadMedida("Código, nombre y abreviatura " "son obligatorios")

        if codigo_normalizado in {
            "BASE",
            "CAJA",
        }:
            raise ErrorUnidadMedida("BASE y CAJA son códigos " "administrados por el producto")

        factor = self._decimal_positivo(
            factor_base,
            "El factor de conversión",
        )

        existente = db.session.scalar(
            db.select(PresentacionProducto.id).where(
                PresentacionProducto.empresa_id == self.usuario.empresa_id,
                PresentacionProducto.producto_id == producto.id,
                PresentacionProducto.codigo == codigo_normalizado,
            )
        )

        if existente is not None:
            raise ErrorUnidadMedida("El código de presentación " "ya existe para este producto")

        presentacion = PresentacionProducto(
            empresa_id=self.usuario.empresa_id,
            producto_id=producto.id,
            codigo=codigo_normalizado,
            nombre=nombre_normalizado,
            abreviatura=abreviatura_normalizada,
            factor_base=factor,
            activa=True,
        )

        try:
            db.session.add(presentacion)
            db.session.commit()
            return presentacion
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorUnidadMedida(
                "La presentación ya existe " "o contiene datos inválidos"
            ) from exc
        except Exception:
            db.session.rollback()
            raise

    def editar(
        self,
        *,
        producto_id: int,
        presentacion_id: int,
        codigo=None,
        nombre=None,
        abreviatura=None,
        factor_base=None,
    ) -> PresentacionProducto:
        self._exigir("productos.editar")
        presentacion = self._obtener_presentacion(
            producto_id=producto_id,
            presentacion_id=presentacion_id,
        )
        self._validar_presentacion_administrada(presentacion)

        codigo_normalizado = str(presentacion.codigo if codigo is None else codigo).strip().upper()
        nombre_normalizado = str(presentacion.nombre if nombre is None else nombre).strip()
        abreviatura_normalizada = str(
            presentacion.abreviatura if abreviatura is None else abreviatura
        ).strip()

        if not codigo_normalizado or not nombre_normalizado or not abreviatura_normalizada:
            raise ErrorUnidadMedida("Código, nombre y abreviatura " "son obligatorios")

        if codigo_normalizado in {
            "BASE",
            "CAJA",
        }:
            raise ErrorUnidadMedida("BASE y CAJA son códigos " "administrados por el producto")

        factor = self._decimal_positivo(
            (presentacion.factor_base if factor_base is None else factor_base),
            "El factor de conversión",
        )

        duplicada = db.session.scalar(
            db.select(PresentacionProducto.id).where(
                PresentacionProducto.empresa_id == self.usuario.empresa_id,
                PresentacionProducto.producto_id == producto_id,
                PresentacionProducto.codigo == codigo_normalizado,
                PresentacionProducto.id != presentacion.id,
            )
        )

        if duplicada is not None:
            raise ErrorUnidadMedida("El código de presentación " "ya existe para este producto")

        presentacion.codigo = codigo_normalizado
        presentacion.nombre = nombre_normalizado
        presentacion.abreviatura = abreviatura_normalizada
        presentacion.factor_base = factor

        try:
            db.session.commit()
            return presentacion
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorUnidadMedida(
                "La presentación ya existe " "o contiene datos inválidos"
            ) from exc
        except Exception:
            db.session.rollback()
            raise

    def desactivar(
        self,
        *,
        producto_id: int,
        presentacion_id: int,
    ) -> PresentacionProducto:
        self._exigir("productos.editar")
        presentacion = self._obtener_presentacion(
            producto_id=producto_id,
            presentacion_id=presentacion_id,
        )
        self._validar_presentacion_administrada(presentacion)

        presentacion.activa = False

        try:
            db.session.commit()
            return presentacion
        except Exception:
            db.session.rollback()
            raise

    def convertir_a_base(
        self,
        *,
        producto_id: int,
        cantidad,
        presentacion_id=None,
    ) -> Decimal:
        self._exigir("productos.ver")
        producto = self._obtener_producto(producto_id)
        cantidad_decimal = self._decimal_positivo(
            cantidad,
            "La cantidad",
        )

        if presentacion_id is None:
            factor = Decimal("1")
        else:
            presentacion = db.session.scalar(
                db.select(PresentacionProducto).where(
                    PresentacionProducto.id == presentacion_id,
                    PresentacionProducto.empresa_id == self.usuario.empresa_id,
                    PresentacionProducto.producto_id == producto.id,
                    PresentacionProducto.activa.is_(True),
                )
            )

            if presentacion is None:
                raise PermissionError("Presentación no encontrada " "en la empresa o producto")

            factor = Decimal(presentacion.factor_base)

        return (cantidad_decimal * factor).quantize(
            PRECISION_CANTIDAD,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def serializar(
        presentacion: PresentacionProducto,
    ) -> dict:
        return {
            "id": presentacion.id,
            "codigo": presentacion.codigo,
            "nombre": presentacion.nombre,
            "abreviatura": presentacion.abreviatura,
            "factor_base": Decimal(presentacion.factor_base),
            "es_base": False,
            "activa": presentacion.activa,
        }

    def _obtener_presentacion(
        self,
        *,
        producto_id: int,
        presentacion_id: int,
    ) -> PresentacionProducto:
        producto = self._obtener_producto(producto_id)

        presentacion = db.session.scalar(
            db.select(PresentacionProducto).where(
                PresentacionProducto.id == presentacion_id,
                PresentacionProducto.empresa_id == self.usuario.empresa_id,
                PresentacionProducto.producto_id == producto.id,
            )
        )

        if presentacion is None:
            raise PermissionError("Presentación no encontrada " "en la empresa o producto")

        return presentacion

    @staticmethod
    def _validar_presentacion_administrada(
        presentacion,
    ) -> None:
        if presentacion.codigo == "CAJA":
            raise ErrorUnidadMedida(
                "La presentación CAJA se " "administra mediante " "unidades_por_caja"
            )

    def _obtener_producto(
        self,
        producto_id: int,
    ) -> Producto:
        producto = db.session.scalar(
            db.select(Producto).where(
                Producto.id == producto_id,
                Producto.empresa_id == self.usuario.empresa_id,
                Producto.eliminado.is_(False),
            )
        )

        if producto is None:
            raise PermissionError("Producto no encontrado " "en la empresa")

        return producto

    @staticmethod
    def _unidad_base(producto) -> dict:
        codigo = str(producto.unidad_medida or "unidad").strip().lower()
        definicion = UNIDADES_BASE.get(codigo)

        if definicion is None:
            definicion = {
                "nombre": codigo.replace(
                    "_",
                    " ",
                ).title(),
                "abreviatura": codigo,
            }

        return {
            "id": None,
            "codigo": "base",
            "nombre": definicion["nombre"],
            "abreviatura": definicion["abreviatura"],
            "factor_base": Decimal("1"),
            "es_base": True,
            "activa": True,
        }

    @staticmethod
    def _decimal_positivo(
        valor,
        nombre: str,
    ) -> Decimal:
        try:
            numero = Decimal(str(valor))
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as exc:
            raise ErrorUnidadMedida(f"{nombre} debe ser numérico") from exc

        if not numero.is_finite() or numero <= 0:
            raise ErrorUnidadMedida(f"{nombre} debe ser mayor que cero")

        return numero.quantize(
            PRECISION_CANTIDAD,
            rounding=ROUND_HALF_UP,
        )

    def _exigir(self, permiso):
        decision = evaluar_permiso(
            self.usuario,
            permiso,
            empresa_id=self.usuario.empresa_id,
        )

        if not decision.permitido:
            raise PermissionError(decision.mensaje)
