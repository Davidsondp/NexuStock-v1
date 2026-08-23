"""Bandeja de notificaciones empresariales por usuario."""

from ..models import Notificacion, Usuario, db, utcnow
from ..permisos import evaluar_permiso


class ErrorNotificacion(ValueError):
    codigo = "notificacion_invalida"


class ServicioNotificaciones:
    def __init__(self, actor):
        self.actor = actor
        if not actor.empresa_id or actor.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def listar(self, *, solo_no_leidas=False, limite=100):
        self._exigir("dashboard.ver")
        try:
            limite = min(max(int(limite), 1), 500)
        except (TypeError, ValueError) as exc:
            raise ErrorNotificacion("El límite no es válido") from exc
        consulta = db.select(Notificacion).where(
            Notificacion.empresa_id == self.actor.empresa_id,
            Notificacion.usuario_id == self.actor.id,
        )
        if solo_no_leidas:
            consulta = consulta.where(Notificacion.leida.is_(False))
        return list(
            db.session.scalars(consulta.order_by(Notificacion.creado_en.desc()).limit(limite))
        )

    def marcar_leida(self, notificacion_id):
        notificacion = self._obtener(notificacion_id)
        if not notificacion.leida:
            notificacion.leida = True
            notificacion.leida_en = utcnow()
            db.session.commit()
        return notificacion

    def marcar_todas_leidas(self):
        notificaciones = self.listar(solo_no_leidas=True, limite=500)
        ahora = utcnow()
        for notificacion in notificaciones:
            notificacion.leida = True
            notificacion.leida_en = ahora
        db.session.commit()
        return len(notificaciones)

    def _obtener(self, notificacion_id):
        notificacion = db.session.scalar(
            db.select(Notificacion).where(
                Notificacion.id == notificacion_id,
                Notificacion.empresa_id == self.actor.empresa_id,
                Notificacion.usuario_id == self.actor.id,
            )
        )
        if not notificacion:
            raise PermissionError("Notificación no autorizada")
        return notificacion

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.actor, permiso, empresa_id=self.actor.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)


def notificar_empresa(
    *, empresa_id, tipo, titulo, mensaje, referencia_tipo=None, referencia_id=None
):
    usuarios = list(
        db.session.scalars(
            db.select(Usuario).where(
                Usuario.empresa_id == empresa_id,
                Usuario.activo.is_(True),
                Usuario.eliminado.is_(False),
                Usuario.rol.in_(("jefe", "supervisor")),
            )
        )
    )
    for usuario in usuarios:
        existente = None
        if referencia_tipo and referencia_id is not None:
            existente = db.session.scalar(
                db.select(Notificacion.id).where(
                    Notificacion.empresa_id == empresa_id,
                    Notificacion.usuario_id == usuario.id,
                    Notificacion.tipo == tipo,
                    Notificacion.referencia_tipo == referencia_tipo,
                    Notificacion.referencia_id == referencia_id,
                )
            )
        if not existente:
            db.session.add(
                Notificacion(
                    empresa_id=empresa_id,
                    usuario_id=usuario.id,
                    tipo=tipo,
                    titulo=titulo,
                    mensaje=mensaje,
                    referencia_tipo=referencia_tipo,
                    referencia_id=referencia_id,
                )
            )
