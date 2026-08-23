from datetime import datetime, time

from flask import has_request_context, request

from ..models import Auditoria, Usuario, db
from ..permisos import evaluar_permiso


def registrar_auditoria(
    *,
    accion: str,
    modulo: str,
    usuario_id=None,
    empresa_id=None,
    entidad_tipo=None,
    entidad_id=None,
    descripcion=None,
    datos_anteriores=None,
    datos_nuevos=None,
) -> Auditoria:
    registro = Auditoria(
        accion=accion,
        modulo=modulo,
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        entidad_tipo=entidad_tipo,
        entidad_id=entidad_id,
        descripcion=descripcion,
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos,
        ip=request.remote_addr if has_request_context() else None,
        agente_usuario=str(request.user_agent)[:500] if has_request_context() else None,
        id_solicitud=request.headers.get("X-Request-ID") if has_request_context() else None,
    )
    db.session.add(registro)
    return registro


class ErrorAuditoria(ValueError):
    codigo = "auditoria_invalida"


class ServicioAuditoriaEmpresa:
    """Consulta de bitácora estrictamente limitada a la empresa del actor."""

    def __init__(self, actor):
        self.actor = actor
        if not actor.empresa_id or actor.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def listar(
        self,
        *,
        modulo=None,
        accion=None,
        usuario_id=None,
        desde=None,
        hasta=None,
        buscar=None,
        limite=200,
    ):
        self._exigir("auditoria.ver")
        try:
            limite = min(max(int(limite), 1), 1000)
        except (TypeError, ValueError) as exc:
            raise ErrorAuditoria("El límite no es válido") from exc
        consulta = db.select(Auditoria).where(Auditoria.empresa_id == self.actor.empresa_id)
        if modulo:
            consulta = consulta.where(Auditoria.modulo == modulo.strip())
        if accion:
            consulta = consulta.where(Auditoria.accion == accion.strip())
        if usuario_id:
            consulta = consulta.where(Auditoria.usuario_id == int(usuario_id))
        if desde:
            consulta = consulta.where(Auditoria.fecha >= self._fecha(desde, final=False))
        if hasta:
            consulta = consulta.where(Auditoria.fecha <= self._fecha(hasta, final=True))
        if buscar:
            patron = f"%{buscar.strip()}%"
            consulta = consulta.where(
                db.or_(
                    Auditoria.accion.ilike(patron),
                    Auditoria.modulo.ilike(patron),
                    Auditoria.descripcion.ilike(patron),
                    Auditoria.entidad_tipo.ilike(patron),
                )
            )
        return list(db.session.scalars(consulta.order_by(Auditoria.fecha.desc()).limit(limite)))

    def usuarios(self):
        self._exigir("auditoria.ver")
        return list(
            db.session.scalars(
                db.select(Usuario)
                .where(
                    Usuario.empresa_id == self.actor.empresa_id,
                    Usuario.eliminado.is_(False),
                )
                .order_by(Usuario.nombre, Usuario.apellido)
            )
        )

    @staticmethod
    def _fecha(valor, *, final):
        try:
            fecha = datetime.strptime(str(valor), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ErrorAuditoria("La fecha debe usar el formato AAAA-MM-DD") from exc
        return datetime.combine(fecha, time.max if final else time.min)

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.actor, permiso, empresa_id=self.actor.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)
