"""Configuración editable por la empresa, separada de plan y facturación."""

from __future__ import annotations

import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError

from ..models import ConfiguracionEmpresa, Empresa, db
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from ..validaciones import normalizar_rut, normalizar_telefono


class ErrorConfiguracion(ValueError):
    codigo = "configuracion_invalida"


IDIOMAS = frozenset({"es", "en"})
MONEDAS = frozenset({"CLP", "USD", "EUR"})
PAISES = frozenset({"CL", "AR", "PE", "CO", "MX", "US", "ES"})
OPCIONES = {
    "mostrar_costos_dashboard": bool,
    "mostrar_stock_cero": bool,
    "decimales_cantidad": int,
    "formato_fecha": str,
}
FORMATOS_FECHA = frozenset({"DD-MM-AAAA", "AAAA-MM-DD", "DD/MM/AAAA"})


class ServicioConfiguracion:
    def __init__(self, usuario):
        self.usuario = usuario
        if not usuario.empresa_id or usuario.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def obtener(self):
        self._exigir("configuracion.ver")
        empresa = db.session.scalar(
            db.select(Empresa).where(
                Empresa.id == self.usuario.empresa_id, Empresa.eliminado.is_(False)
            )
        )
        if not empresa:
            raise PermissionError("Empresa no autorizada")
        if empresa.configuracion is None:
            empresa.configuracion = ConfiguracionEmpresa(
                empresa_id=empresa.id, nombre_comercial=empresa.nombre
            )
            db.session.flush()
        return empresa, empresa.configuracion

    def editar_empresa(self, **datos):
        self._exigir("empresa.editar")
        empresa, _ = self.obtener()
        anteriores = self._empresa_dict(empresa)
        permitidos = {
            "nombre",
            "identificacion_fiscal",
            "email",
            "telefono",
            "direccion",
            "ciudad",
            "pais",
            "moneda",
            "idioma",
            "zona_horaria",
        }
        desconocidos = set(datos) - permitidos
        if desconocidos:
            raise ErrorConfiguracion(
                f"Campos empresariales no editables: {', '.join(sorted(desconocidos))}"
            )
        try:
            if "nombre" in datos:
                empresa.nombre = self._obligatorio(datos["nombre"], "El nombre")
            if "identificacion_fiscal" in datos:
                try:
                    empresa.identificacion_fiscal = normalizar_rut(datos["identificacion_fiscal"])
                except ValueError as exc:
                    raise ErrorConfiguracion(str(exc)) from exc
            if "email" in datos:
                empresa.email = self._email(datos["email"])
            if "telefono" in datos:
                try:
                    empresa.telefono = normalizar_telefono(datos["telefono"])
                except ValueError as exc:
                    raise ErrorConfiguracion(str(exc)) from exc
            for campo in ("direccion", "ciudad"):
                if campo in datos:
                    setattr(empresa, campo, (datos[campo] or "").strip() or None)
            if "pais" in datos:
                pais = (datos["pais"] or "").upper()
                if pais not in PAISES:
                    raise ErrorConfiguracion("País no admitido")
                empresa.pais = pais
            if "moneda" in datos:
                moneda = (datos["moneda"] or "").upper()
                if moneda not in MONEDAS:
                    raise ErrorConfiguracion("Moneda no admitida")
                empresa.moneda = moneda
            if "idioma" in datos:
                idioma = (datos["idioma"] or "").lower()
                if idioma not in IDIOMAS:
                    raise ErrorConfiguracion("Idioma no admitido")
                empresa.idioma = idioma
            if "zona_horaria" in datos:
                zona = self._zona_horaria(datos["zona_horaria"])
                empresa.zona_horaria = zona
            self._auditar(
                "empresa.editada", "Empresa", empresa.id, anteriores, self._empresa_dict(empresa)
            )
            db.session.commit()
            return empresa
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorConfiguracion(
                "El correo o identificación fiscal ya está registrado"
            ) from exc
        except Exception:
            db.session.rollback()
            raise

    def editar_preferencias(self, **datos):
        self._exigir("configuracion.editar")
        empresa, configuracion = self.obtener()
        anteriores = self._configuracion_dict(configuracion)
        permitidos = {
            "nombre_comercial",
            "logo_url",
            "color_principal",
            "alerta_stock_bajo",
            "alerta_sobrestock",
            "dias_sin_movimiento",
            "opciones",
        }
        desconocidos = set(datos) - permitidos
        if desconocidos:
            raise ErrorConfiguracion(
                f"Campos de configuración no editables: {', '.join(sorted(desconocidos))}"
            )
        if "nombre_comercial" in datos:
            configuracion.nombre_comercial = self._obligatorio(
                datos["nombre_comercial"], "El nombre comercial"
            )
        if "logo_url" in datos:
            configuracion.logo_url = self._url_https(datos["logo_url"])
        if "color_principal" in datos:
            color = (datos["color_principal"] or "").upper()
            if not re.fullmatch(r"#[0-9A-F]{6}", color):
                raise ErrorConfiguracion("El color principal debe tener formato #RRGGBB")
            configuracion.color_principal = color
        for campo in ("alerta_stock_bajo", "alerta_sobrestock"):
            if campo in datos:
                if not isinstance(datos[campo], bool):
                    raise ErrorConfiguracion(f"{campo} debe ser booleano")
                setattr(configuracion, campo, datos[campo])
        if "dias_sin_movimiento" in datos:
            try:
                dias = int(datos["dias_sin_movimiento"])
            except (TypeError, ValueError) as exc:
                raise ErrorConfiguracion("Los días sin movimiento no son válidos") from exc
            if not 1 <= dias <= 3650:
                raise ErrorConfiguracion("Los días sin movimiento deben estar entre 1 y 3650")
            configuracion.dias_sin_movimiento = dias
        if "opciones" in datos:
            configuracion.opciones = self._opciones(datos["opciones"])
        self._auditar(
            "configuracion.editada",
            "ConfiguracionEmpresa",
            configuracion.id,
            anteriores,
            self._configuracion_dict(configuracion),
        )
        db.session.commit()
        return empresa, configuracion

    def resumen(self):
        empresa, configuracion = self.obtener()
        suscripcion = empresa.suscripcion_actual
        return {
            "empresa": self._empresa_dict(empresa),
            "preferencias": self._configuracion_dict(configuracion),
            "suscripcion": {
                "plan": suscripcion.plan.nombre,
                "codigo_plan": suscripcion.plan.codigo,
                "estado": suscripcion.estado,
                "limites": {
                    "productos": suscripcion.plan.limite_productos,
                    "usuarios": suscripcion.plan.limite_usuarios,
                    "movimientos_mes": suscripcion.plan.limite_movimientos_mes,
                    "sucursales": suscripcion.plan.limite_sucursales,
                    "bodegas": suscripcion.plan.limite_bodegas,
                },
            },
        }

    @staticmethod
    def _empresa_dict(e):
        return {
            "nombre": e.nombre,
            "identificacion_fiscal": e.identificacion_fiscal,
            "email": e.email,
            "telefono": e.telefono,
            "direccion": e.direccion,
            "ciudad": e.ciudad,
            "pais": e.pais,
            "moneda": e.moneda,
            "idioma": e.idioma,
            "zona_horaria": e.zona_horaria,
        }

    @staticmethod
    def _configuracion_dict(c):
        return {
            "nombre_comercial": c.nombre_comercial,
            "logo_url": c.logo_url,
            "color_principal": c.color_principal,
            "alerta_stock_bajo": c.alerta_stock_bajo,
            "alerta_sobrestock": c.alerta_sobrestock,
            "dias_sin_movimiento": c.dias_sin_movimiento,
            "opciones": c.opciones or {},
        }

    @staticmethod
    def _obligatorio(valor, nombre):
        valor = (valor or "").strip()
        if not valor:
            raise ErrorConfiguracion(f"{nombre} es obligatorio")
        return valor

    @staticmethod
    def _email(valor):
        valor = (valor or "").strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", valor):
            raise ErrorConfiguracion("Correo inválido")
        return valor

    @staticmethod
    def _zona_horaria(valor):
        zona = (valor or "").strip()
        try:
            ZoneInfo(zona)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ErrorConfiguracion("Zona horaria inválida") from exc
        return zona

    @staticmethod
    def _url_https(valor):
        valor = (valor or "").strip()
        if not valor:
            return None
        partes = urlparse(valor)
        if partes.scheme != "https" or not partes.netloc or partes.username or partes.password:
            raise ErrorConfiguracion("El logo debe usar una URL HTTPS pública")
        return valor

    @staticmethod
    def _opciones(opciones):
        if not isinstance(opciones, dict):
            raise ErrorConfiguracion("Las opciones deben ser un objeto")
        desconocidas = set(opciones) - set(OPCIONES)
        if desconocidas:
            raise ErrorConfiguracion(f"Opciones desconocidas: {', '.join(sorted(desconocidas))}")
        resultado = {}
        for clave, valor in opciones.items():
            esperado = OPCIONES[clave]
            if esperado is int:
                if (
                    isinstance(valor, bool)
                    or not isinstance(valor, int)
                    or valor not in {0, 1, 2, 3}
                ):
                    raise ErrorConfiguracion("decimales_cantidad debe estar entre 0 y 3")
            elif esperado is str:
                if valor not in FORMATOS_FECHA:
                    raise ErrorConfiguracion("Formato de fecha no admitido")
            elif not isinstance(valor, esperado):
                raise ErrorConfiguracion(f"{clave} tiene un valor inválido")
            resultado[clave] = valor
        return resultado

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.usuario, permiso, empresa_id=self.usuario.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)

    def _auditar(self, accion, tipo, entidad_id, anteriores, nuevos):
        registrar_auditoria(
            accion=accion,
            modulo="configuracion",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo=tipo,
            entidad_id=entidad_id,
            datos_anteriores=anteriores,
            datos_nuevos=nuevos,
        )
