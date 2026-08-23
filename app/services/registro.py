from datetime import timedelta
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from ..catalogo_planes import PLANES_AUTOSERVICIO
from ..models import (
    Bodega,
    ConfiguracionEmpresa,
    Empresa,
    PlanSaaS,
    SolicitudCambioPlan,
    Sucursal,
    Suscripcion,
    Usuario,
    UsuarioSucursal,
    db,
    utcnow,
)
from .auditoria import registrar_auditoria
from .perfiles_empresa import CAPACIDADES_POR_RUBRO
from ..validaciones import normalizar_rut, normalizar_telefono


class ErrorRegistro(ValueError):
    pass


def _plan_comercial(
    plan_codigo: str | None,
    ciclo: str | None,
) -> tuple[PlanSaaS | None, str | None]:
    if plan_codigo is None and ciclo is None:
        return None, None

    codigo = str(plan_codigo or "").strip().lower()
    ciclo_normalizado = str(ciclo or "").strip().lower()

    if ciclo_normalizado not in {
        "mensual",
        "anual",
    }:
        raise ErrorRegistro("El ciclo comercial no es válido")

    plan = db.session.scalar(
        db.select(PlanSaaS).where(
            PlanSaaS.codigo == codigo,
            PlanSaaS.activo.is_(True),
            PlanSaaS.codigo.in_(PLANES_AUTOSERVICIO),
        )
    )

    if not plan:
        raise ErrorRegistro("El plan comercial no está disponible")

    return plan, ciclo_normalizado


def registrar_empresa(
    *,
    empresa_nombre: str,
    identificacion_fiscal: str | None,
    nombre: str,
    apellido: str | None,
    email: str,
    password: str,
    empresa_identificacion_fiscal: str | None = None,
    telefono: str | None = None,
    empresa_telefono: str | None = None,
    rubro: str | None = "general",
    plan_codigo: str | None = None,
    ciclo: str | None = None,
    proveedor: str | None = None,
) -> Usuario:
    """Crea el tenant inicial completo en una transacción."""

    plan_prueba_legado = db.session.scalar(
        db.select(PlanSaaS).where(
            PlanSaaS.codigo == "prueba",
        )
    )

    plan_comercial, ciclo_comercial = _plan_comercial(
        plan_codigo,
        ciclo,
    )
    proveedor_comercial = str(proveedor or "").strip().lower() or None
    if plan_comercial and proveedor_comercial not in {
        "webpay",
        "mercadopago",
    }:
        raise ErrorRegistro("El proveedor de pago no es válido")
    if not plan_comercial:
        proveedor_comercial = None
        if not plan_prueba_legado:
            raise ErrorRegistro("Selecciona uno de los planes disponibles")

    codigo_rubro = str(rubro or "general").strip().lower()

    if codigo_rubro not in CAPACIDADES_POR_RUBRO:
        raise ErrorRegistro("El rubro de la empresa no es válido")

    email = email.strip().lower()

    if db.session.scalar(db.select(Usuario.id).where(Usuario.email == email)):
        raise ErrorRegistro("El correo ya está registrado")

    try:
        empresa = Empresa(
            nombre=empresa_nombre.strip(),
            identificacion_fiscal=normalizar_rut(empresa_identificacion_fiscal),
            email=email,
            telefono=normalizar_telefono(empresa_telefono),
            estado="activa",
        )
        db.session.add(empresa)
        db.session.flush()

        ahora = utcnow()

        plan_inicial = plan_comercial or plan_prueba_legado
        dias_prueba = int(plan_comercial.dias_prueba or 30) if plan_comercial else 30
        requiere_mandato = bool(plan_comercial)
        suscripcion = Suscripcion(
            empresa_id=empresa.id,
            plan_id=plan_inicial.id,
            estado="prueba",
            ciclo="prueba",
            fecha_inicio=ahora,
            # En autoservicio estas fechas se fijan al confirmar la tarjeta.
            # Así los 30 días no se consumen antes de completar la autorización.
            fecha_fin=(None if requiere_mandato else ahora + timedelta(days=dias_prueba)),
            periodo_actual_inicio=(None if requiere_mandato else ahora),
            periodo_actual_fin=(None if requiere_mandato else ahora + timedelta(days=dias_prueba)),
            # Se activa sólo después de que el proveedor confirme el mandato tokenizado.
            renovacion_automatica=False,
            proveedor_cobro=proveedor_comercial,
            metodo_pago_recurrente_estado=("pendiente" if requiere_mandato else "no_requerido"),
        )
        sucursal = Sucursal(
            empresa_id=empresa.id,
            codigo="PRINCIPAL",
            nombre="Sucursal principal",
        )
        configuracion = ConfiguracionEmpresa(
            empresa_id=empresa.id,
            nombre_comercial=empresa.nombre,
            opciones={
                "rubro": codigo_rubro,
                "capacidades": {},
            },
        )

        db.session.add_all(
            [
                suscripcion,
                sucursal,
                configuracion,
            ]
        )
        db.session.flush()

        bodega = Bodega(
            empresa_id=empresa.id,
            sucursal_id=sucursal.id,
            codigo="PRINCIPAL",
            nombre="Bodega principal",
        )
        usuario = Usuario(
            empresa_id=empresa.id,
            nombre=nombre.strip(),
            apellido=((apellido or "").strip() or None),
            identificacion_fiscal=normalizar_rut(identificacion_fiscal),
            telefono=normalizar_telefono(telefono),
            email=email,
            rol="jefe",
            activo=True,
        )
        usuario.set_password(password)

        db.session.add_all(
            [
                bodega,
                usuario,
            ]
        )
        db.session.flush()

        db.session.add(
            UsuarioSucursal(
                empresa_id=empresa.id,
                usuario_id=usuario.id,
                sucursal_id=sucursal.id,
                es_principal=True,
            )
        )

        if plan_comercial and ciclo_comercial:
            precio = (
                plan_comercial.precio_mensual
                if ciclo_comercial == "mensual"
                else plan_comercial.precio_anual
            )
            monto = Decimal(precio).quantize(Decimal("0.01"))

            solicitud = SolicitudCambioPlan(
                empresa_id=empresa.id,
                plan_solicitado_id=(plan_comercial.id),
                solicitada_por_id=usuario.id,
                estado="pendiente",
                ciclo=ciclo_comercial,
                monto_esperado=monto,
                moneda=plan_comercial.moneda,
                proveedor_preferido=proveedor_comercial,
            )
            db.session.add(solicitud)
            db.session.flush()

            registrar_auditoria(
                accion="suscripcion.solicitada",
                modulo="suscripciones",
                empresa_id=empresa.id,
                usuario_id=usuario.id,
                entidad_tipo=("SolicitudCambioPlan"),
                entidad_id=solicitud.id,
                datos_nuevos={
                    "plan": plan_comercial.codigo,
                    "ciclo": ciclo_comercial,
                    "monto": str(monto),
                },
            )

        registrar_auditoria(
            accion="empresa.registro",
            modulo="autenticacion",
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            entidad_tipo="Empresa",
            entidad_id=empresa.id,
            descripcion=("Registro inicial de empresa " "y su jefatura"),
        )

        db.session.commit()
        return usuario

    except IntegrityError as exc:
        db.session.rollback()
        raise ErrorRegistro("El correo o la identificación fiscal " "ya están registrados") from exc

    except ValueError as exc:
        db.session.rollback()
        raise ErrorRegistro(str(exc)) from exc

    except Exception:
        db.session.rollback()
        raise
