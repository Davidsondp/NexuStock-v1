from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_user, logout_user

from ...catalogo_planes import PLANES_AUTOSERVICIO
from ...models import PlanSaaS, Usuario, db
from ...services.auditoria import registrar_auditoria
from ...services.registro import ErrorRegistro, registrar_empresa
from ...services.restablecimiento import (
    buscar_usuario_por_token,
    restablecer_password,
    solicitar_restablecimiento,
)
from ...services.seguridad_cuenta import (
    ErrorEntregaCorreo,
    ErrorSeguridadCuenta,
    confirmar_2fa,
    confirmar_verificacion,
    desactivar_2fa,
    emitir_verificacion,
    iniciar_2fa,
    verificar_2fa,
)
from .forms import (
    LoginForm,
    RegistroForm,
    RestablecerPasswordForm,
    SolicitarRestablecimientoForm,
)

autenticacion_bp = Blueprint(
    "autenticacion",
    __name__,
    url_prefix="/autenticacion",
)

CLAVE_PLAN_REGISTRO = "registro_plan_seleccionado"
CLAVE_CICLO_REGISTRO = "registro_ciclo_seleccionado"
CLAVE_PROVEEDOR_REGISTRO = "registro_proveedor_seleccionado"
CICLOS_COMERCIALES = {
    "mensual",
    "anual",
}


def _limpiar_seleccion_registro() -> None:
    session.pop(
        CLAVE_PLAN_REGISTRO,
        None,
    )
    session.pop(
        CLAVE_CICLO_REGISTRO,
        None,
    )
    session.pop(CLAVE_PROVEEDOR_REGISTRO, None)


def _seleccion_registro():
    if request.method == "GET" and ("plan" in request.args or "ciclo" in request.args):
        codigo = str(request.args.get("plan") or "").strip().lower()
        ciclo = str(request.args.get("ciclo") or "").strip().lower()
        proveedor = str(request.args.get("proveedor") or "").strip().lower()

        plan = db.session.scalar(
            db.select(PlanSaaS).where(
                PlanSaaS.codigo == codigo,
                PlanSaaS.activo.is_(True),
                PlanSaaS.codigo.in_(PLANES_AUTOSERVICIO),
            )
        )

        if (
            not plan
            or ciclo not in CICLOS_COMERCIALES
            or proveedor not in {"webpay", "mercadopago"}
        ):
            _limpiar_seleccion_registro()
            return None, None, None

        session[CLAVE_PLAN_REGISTRO] = plan.codigo
        session[CLAVE_CICLO_REGISTRO] = ciclo
        session[CLAVE_PROVEEDOR_REGISTRO] = proveedor
        return plan, ciclo, proveedor

    codigo = session.get(CLAVE_PLAN_REGISTRO)
    ciclo = session.get(CLAVE_CICLO_REGISTRO)
    proveedor = session.get(CLAVE_PROVEEDOR_REGISTRO)

    if not codigo and current_app.config.get("REQUIRE_TRIAL_PAYMENT_METHOD", True):
        codigo, ciclo, proveedor = "avanzado", "mensual", "mercadopago"
        session[CLAVE_PLAN_REGISTRO] = codigo
        session[CLAVE_CICLO_REGISTRO] = ciclo
        session[CLAVE_PROVEEDOR_REGISTRO] = proveedor
    if (
        not codigo
        or ciclo not in CICLOS_COMERCIALES
        or proveedor
        not in {
            "webpay",
            "mercadopago",
        }
    ):
        _limpiar_seleccion_registro()
        return None, None, None

    plan = db.session.scalar(
        db.select(PlanSaaS).where(
            PlanSaaS.codigo == codigo,
            PlanSaaS.activo.is_(True),
            PlanSaaS.codigo.in_(PLANES_AUTOSERVICIO),
        )
    )

    if not plan:
        _limpiar_seleccion_registro()
        return None, None, None

    return plan, ciclo, proveedor


def _destino_seguro(destino: str | None) -> str | None:
    if destino and destino.startswith("/") and not destino.startswith("//"):
        return destino
    return None


def _destino_usuario(usuario: Usuario) -> str:
    """Obtiene el destino inicial según el ámbito del usuario."""

    if usuario.rol == "super_admin" and usuario.empresa_id is None:
        return url_for("panel_superadministracion.inicio")

    if usuario.rol == "jefe" and usuario.empresa and not usuario.empresa.suscripcion_actual:
        return url_for("panel.administracion_planes")

    return url_for("panel.inicio")


@autenticacion_bp.route("/registro", methods=["GET", "POST"])
def registro():
    if current_user.is_authenticated:
        return redirect(_destino_usuario(current_user))

    formulario = RegistroForm()
    plan_seleccionado, ciclo_seleccionado, proveedor_seleccionado = _seleccion_registro()

    if formulario.validate_on_submit():
        try:
            usuario = registrar_empresa(
                empresa_nombre=(formulario.empresa_nombre.data),
                rubro=formulario.rubro.data,
                identificacion_fiscal=(formulario.identificacion_fiscal.data),
                empresa_identificacion_fiscal=(formulario.empresa_identificacion_fiscal.data),
                nombre=formulario.nombre.data,
                apellido=formulario.apellido.data,
                telefono=formulario.telefono.data,
                empresa_telefono=formulario.empresa_telefono.data,
                email=formulario.email.data,
                password=formulario.password.data,
                plan_codigo=(plan_seleccionado.codigo if plan_seleccionado else None),
                ciclo=ciclo_seleccionado,
                proveedor=proveedor_seleccionado,
            )

            _limpiar_seleccion_registro()
            try:
                emitir_verificacion(usuario)
                flash(
                    "Tu empresa fue creada. Revisa tu correo y abre el enlace de verificación.",
                    "exito",
                )
            except ErrorEntregaCorreo as exc:
                flash(str(exc), "peligro")
            if not current_app.config.get("REQUIRE_EMAIL_VERIFICATION", True):
                login_user(usuario)
                return redirect(_destino_usuario(usuario))
            return redirect(url_for("autenticacion.ingresar"))

        except ErrorRegistro as excepcion:
            flash(str(excepcion), "peligro")

    return render_template(
        "autenticacion/registro.html",
        form=formulario,
        plan_seleccionado=plan_seleccionado,
        ciclo_seleccionado=ciclo_seleccionado,
        proveedor_seleccionado=proveedor_seleccionado,
    )


@autenticacion_bp.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    if current_user.is_authenticated:
        return redirect(_destino_usuario(current_user))

    formulario = LoginForm()

    if formulario.validate_on_submit():
        email = formulario.email.data.strip().lower()

        usuario = db.session.scalar(db.select(Usuario).where(Usuario.email == email))

        if usuario and usuario.esta_bloqueado():
            flash(
                "Cuenta temporalmente bloqueada. Intenta más tarde.",
                "peligro",
            )

        elif not usuario or not usuario.check_password(formulario.password.data):
            if usuario:
                usuario.registrar_intento_fallido()
                db.session.commit()

            flash("Credenciales inválidas.", "peligro")

        elif not usuario.is_active or (usuario.empresa and not usuario.empresa.esta_activa()):
            flash("La cuenta no está habilitada.", "peligro")

        elif (
            current_app.config.get("REQUIRE_EMAIL_VERIFICATION", True)
            and not usuario.email_verificado
        ):
            flash("Debes verificar tu correo antes de ingresar.", "peligro")

        else:
            if usuario.two_factor_enabled:
                session["2fa_usuario_id"] = usuario.id
                session["2fa_recordar"] = bool(formulario.recordar.data)
                session["2fa_destino"] = _destino_seguro(request.args.get("siguiente"))
                return redirect(url_for("autenticacion.segundo_factor"))

            _registrar_ingreso_exitoso(usuario)
            login_user(
                usuario,
                remember=formulario.recordar.data,
            )

            destino_solicitado = _destino_seguro(request.args.get("siguiente"))

            # Un Super Admin siempre entra en su panel global.
            # Nunca se redirige hacia módulos empresariales.
            if usuario.rol == "super_admin":
                destino_solicitado = None

            return redirect(destino_solicitado or _destino_usuario(usuario))

    return render_template(
        "autenticacion/ingresar.html",
        form=formulario,
    )


@autenticacion_bp.route("/segundo-factor", methods=["GET", "POST"])
def segundo_factor():
    usuario_id = session.get("2fa_usuario_id")
    usuario = db.session.get(Usuario, usuario_id) if usuario_id else None
    if not usuario or not usuario.two_factor_enabled:
        session.pop("2fa_usuario_id", None)
        return redirect(url_for("autenticacion.ingresar"))
    if request.method == "POST":
        if verificar_2fa(usuario, request.form.get("codigo")):
            recordar = bool(session.pop("2fa_recordar", False))
            destino = session.pop("2fa_destino", None)
            session.pop("2fa_usuario_id", None)
            _registrar_ingreso_exitoso(usuario)
            login_user(usuario, remember=recordar)
            return redirect(destino or _destino_usuario(usuario))
        flash("Código de segundo factor inválido.", "peligro")
    return render_template("autenticacion/segundo_factor.html")


def _registrar_ingreso_exitoso(usuario):
    """Sólo registra acceso después de completar todos los factores."""
    usuario.registrar_acceso()
    registrar_auditoria(
        accion="usuario.ingreso",
        modulo="autenticacion",
        usuario_id=usuario.id,
        empresa_id=usuario.empresa_id,
        entidad_tipo="Usuario",
        entidad_id=usuario.id,
    )
    db.session.commit()


@autenticacion_bp.get("/verificar-correo/<token>")
def verificar_correo(token):
    try:
        confirmar_verificacion(token)
        flash("Correo verificado correctamente.", "exito")
    except ErrorSeguridadCuenta as exc:
        flash(str(exc), "peligro")
    return redirect(url_for("autenticacion.ingresar"))


@autenticacion_bp.post("/reenviar-verificacion")
def reenviar_verificacion():
    usuario = current_user if current_user.is_authenticated else None
    if not usuario:
        email = str(request.form.get("email") or "").strip().lower()
        usuario = db.session.scalar(db.select(Usuario).where(Usuario.email == email))
    if usuario and not usuario.email_verificado:
        try:
            emitir_verificacion(usuario)
        except ErrorEntregaCorreo as exc:
            flash(str(exc), "peligro")
            return redirect(url_for("autenticacion.ingresar"))
    flash(
        "Si la cuenta existe y está pendiente, enviamos un nuevo enlace de verificación.",
        "exito",
    )
    return redirect(
        url_for("autenticacion.seguridad_cuenta")
        if current_user.is_authenticated
        else url_for("autenticacion.ingresar")
    )


@autenticacion_bp.route("/seguridad", methods=["GET", "POST"])
def seguridad_cuenta():
    if not current_user.is_authenticated:
        return redirect(url_for("autenticacion.ingresar"))
    secreto = session.get("2fa_configuracion_secreto")
    if request.method == "POST":
        accion = request.form.get("accion")
        try:
            if accion == "iniciar":
                secreto = iniciar_2fa(current_user)
                session["2fa_configuracion_secreto"] = secreto
            elif accion == "confirmar":
                confirmar_2fa(current_user, request.form.get("codigo"))
                session.pop("2fa_configuracion_secreto", None)
                flash("Segundo factor activado.", "exito")
                return redirect(url_for("autenticacion.seguridad_cuenta"))
            elif accion == "desactivar":
                desactivar_2fa(
                    current_user, request.form.get("password"), request.form.get("codigo")
                )
                flash("Segundo factor desactivado.", "exito")
                return redirect(url_for("autenticacion.ingresar"))
        except ErrorSeguridadCuenta as exc:
            flash(str(exc), "peligro")
    uri = None
    if secreto:
        import urllib.parse

        uri = (
            "otpauth://totp/NexuStock:"
            f"{urllib.parse.quote(current_user.email)}?secret={secreto}&issuer=NexuStock"
        )
    return render_template("autenticacion/seguridad.html", secreto=secreto, uri=uri)


@autenticacion_bp.post("/salir")
def salir():
    if current_user.is_authenticated:
        registrar_auditoria(
            accion="usuario.salida",
            modulo="autenticacion",
            usuario_id=current_user.id,
            empresa_id=current_user.empresa_id,
            entidad_tipo="Usuario",
            entidad_id=current_user.id,
        )

        db.session.commit()
        logout_user()

    return redirect(url_for("autenticacion.ingresar"))


@autenticacion_bp.route(
    "/olvide-password",
    methods=["GET", "POST"],
)
def olvide_password():
    if current_user.is_authenticated:
        return redirect(_destino_usuario(current_user))

    formulario = SolicitarRestablecimientoForm()

    if formulario.validate_on_submit():
        solicitar_restablecimiento(formulario.email.data)

        flash(
            "Si el correo está registrado, recibirás instrucciones "
            "para restablecer tu contraseña.",
            "exito",
        )

        return redirect(url_for("autenticacion.ingresar"))

    return render_template(
        "autenticacion/olvide_password.html",
        form=formulario,
    )


@autenticacion_bp.route(
    "/restablecer-password/<token>",
    methods=["GET", "POST"],
)
def restablecer_password_route(token: str):
    if current_user.is_authenticated:
        return redirect(_destino_usuario(current_user))

    usuario = buscar_usuario_por_token(token)

    if not usuario:
        flash(
            "El enlace es inválido o ha expirado.",
            "peligro",
        )
        return redirect(url_for("autenticacion.olvide_password"))

    formulario = RestablecerPasswordForm()

    if formulario.validate_on_submit():
        actualizado = restablecer_password(
            usuario,
            token,
            formulario.password.data,
        )

        if actualizado:
            flash(
                "Tu contraseña fue actualizada. Ya puedes ingresar.",
                "exito",
            )
            return redirect(url_for("autenticacion.ingresar"))

        flash(
            "El enlace es inválido o ha expirado.",
            "peligro",
        )
        return redirect(url_for("autenticacion.olvide_password"))

    return render_template(
        "autenticacion/restablecer_password.html",
        form=formulario,
    )
