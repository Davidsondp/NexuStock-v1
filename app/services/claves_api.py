"""Emisión y validación de claves API empresariales."""

from datetime import datetime
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from ..models import ClaveApi, Producto, db, utcnow
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria

SCOPES = frozenset({"productos:leer", "stock:leer", "movimientos:leer"})


class ErrorClaveApi(ValueError):
    codigo = "clave_api_invalida"


class ServicioClavesApi:
    MAXIMO = 10

    def __init__(self, actor):
        self.actor = actor
        if not actor.empresa_id or actor.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def listar(self):
        self._exigir("api.gestionar")
        return list(
            db.session.scalars(
                db.select(ClaveApi)
                .where(ClaveApi.empresa_id == self.actor.empresa_id)
                .order_by(ClaveApi.creado_en.desc())
            )
        )

    def crear(self, *, nombre, permisos, expira_en=None):
        self._exigir("api.gestionar")
        if len(self.listar()) >= self.MAXIMO:
            raise ErrorClaveApi(f"Cada empresa admite hasta {self.MAXIMO} claves API")
        nombre = (nombre or "").strip()
        if not nombre:
            raise ErrorClaveApi("El nombre es obligatorio")
        if not isinstance(permisos, list):
            raise ErrorClaveApi("Los permisos deben ser una lista")
        scopes = set(permisos)
        if not scopes or not scopes.issubset(SCOPES):
            raise ErrorClaveApi("Uno o más permisos API no son válidos")
        expiracion = None
        if expira_en:
            try:
                expiracion = datetime.fromisoformat(str(expira_en).replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
            except ValueError as exc:
                raise ErrorClaveApi("La expiración no es válida") from exc
            if expiracion <= utcnow():
                raise ErrorClaveApi("La expiración debe ser futura")
        prefijo = secrets.token_hex(6)
        secreto = secrets.token_urlsafe(32)
        token = f"nxs_{prefijo}_{secreto}"
        clave = ClaveApi(
            empresa_id=self.actor.empresa_id,
            nombre=nombre,
            prefijo=prefijo,
            secreto_hash=generate_password_hash(token),
            permisos={scope: True for scope in sorted(scopes)},
            activa=True,
            expira_en=expiracion,
        )
        db.session.add(clave)
        db.session.flush()
        self._auditar(clave, "creada")
        db.session.commit()
        return clave, token

    def revocar(self, clave_id):
        self._exigir("api.gestionar")
        clave = self._obtener(clave_id)
        clave.activa = False
        self._auditar(clave, "revocada")
        db.session.commit()
        return clave

    def _obtener(self, clave_id):
        clave = db.session.scalar(
            db.select(ClaveApi).where(
                ClaveApi.id == clave_id, ClaveApi.empresa_id == self.actor.empresa_id
            )
        )
        if not clave:
            raise PermissionError("Clave API no autorizada")
        return clave

    def _auditar(self, clave, accion):
        registrar_auditoria(
            accion=f"api.clave_{accion}",
            modulo="api",
            usuario_id=self.actor.id,
            empresa_id=self.actor.empresa_id,
            entidad_tipo="ClaveApi",
            entidad_id=clave.id,
            datos_nuevos={"nombre": clave.nombre, "prefijo": clave.prefijo},
        )

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.actor, permiso, empresa_id=self.actor.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)


def autenticar_clave(token, scope):
    if not token or not token.startswith("nxs_") or len(token.split("_", 2)) != 3:
        raise PermissionError("Clave API inválida")
    prefijo = token.split("_", 2)[1]
    clave = db.session.scalar(db.select(ClaveApi).where(ClaveApi.prefijo == prefijo))
    ahora = utcnow()
    if (
        not clave
        or not clave.activa
        or (clave.expira_en and clave.expira_en <= ahora)
        or not check_password_hash(clave.secreto_hash, token)
        or not (clave.permisos or {}).get(scope)
        or not clave.empresa.esta_activa()
        or not clave.empresa.suscripcion_actual
        or not clave.empresa.suscripcion_actual.plan.tiene_funcion("api")
    ):
        raise PermissionError("Clave API inválida, vencida o sin permiso")
    clave.ultimo_uso = ahora
    db.session.commit()
    return clave


def productos_publicos(clave):
    return list(
        db.session.scalars(
            db.select(Producto)
            .where(
                Producto.empresa_id == clave.empresa_id,
                Producto.activo.is_(True),
                Producto.eliminado.is_(False),
            )
            .order_by(Producto.nombre)
            .limit(1000)
        )
    )
