import os
import re

from flask import (
    Flask,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    send_from_directory,
    url_for,
)
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from config import CONFIGURACIONES
from .catalogo_planes import PLANES_PAGADOS_PUBLICOS
from .extensions import correo, csrf, login_manager, migrate
from .models import PlanSaaS, SolicitudContratoEmpresarial, Suscripcion, Usuario, db


def crear_aplicacion(nombre_configuracion: str | None = None) -> Flask:
    entorno = nombre_configuracion or os.getenv("FLASK_ENV", "desarrollo")
    clase_configuracion = CONFIGURACIONES.get(entorno, CONFIGURACIONES["desarrollo"])
    if entorno == "produccion":
        clase_configuracion.validar()

    app = Flask(__name__)
    app.config.from_object(clase_configuracion)
    if app.config.get("TRUST_PROXY_HEADERS"):
        # Render termina TLS delante de Gunicorn. Sólo se confía en un salto de
        # proxy para recuperar la IP y el esquema originales, nunca el host.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    correo.init_app(app)
    from .seguridad import registrar_seguridad

    registrar_seguridad(app)
    login_manager.login_view = "autenticacion.ingresar"

    from .blueprints.estado.routes import estado_bp
    from .blueprints.autenticacion.routes import autenticacion_bp
    from .blueprints.contexto.routes import contexto_bp
    from .blueprints.productos.routes import productos_bp
    from .blueprints.inventario.routes import inventario_bp
    from .blueprints.proveedores.routes import proveedores_bp
    from .blueprints.ubicaciones.routes import ubicaciones_bp
    from .blueprints.compras.routes import compras_bp
    from .blueprints.ventas.routes import ventas_bp
    from .blueprints.transferencias.routes import transferencias_bp
    from .blueprints.seriales.routes import seriales_bp
    from .blueprints.auditoria.routes import auditoria_bp
    from .blueprints.claves_api.routes import claves_api_bp
    from .blueprints.api_publica.routes import api_publica_bp
    from .blueprints.notificaciones.routes import notificaciones_bp
    from .blueprints.reportes_personalizados.routes import reportes_personalizados_bp
    from .blueprints.asistente_ia.routes import asistente_ia_bp
    from .blueprints.importaciones.routes import importaciones_bp
    from .blueprints.ayuda.routes import ayuda_bp
    from .blueprints.clientes.routes import clientes_bp
    from .blueprints.alertas.routes import alertas_bp
    from .blueprints.reportes.routes import reportes_bp
    from .blueprints.usuarios.routes import usuarios_bp
    from .blueprints.configuracion.routes import configuracion_bp
    from .blueprints.suscripciones.routes import suscripciones_bp, webhooks_pago_bp
    from .blueprints.suite_comercial.routes import suite_comercial_bp, integraciones_webhook_bp
    from .blueprints.superadministracion.routes import superadministracion_bp
    from .blueprints.superadministracion.panel import panel_superadministracion_bp
    from .blueprints.panel.routes import panel_bp

    app.register_blueprint(estado_bp)
    app.register_blueprint(autenticacion_bp)
    app.register_blueprint(contexto_bp)
    app.register_blueprint(productos_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(proveedores_bp)
    app.register_blueprint(ubicaciones_bp)
    app.register_blueprint(compras_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(transferencias_bp)
    app.register_blueprint(seriales_bp)
    app.register_blueprint(auditoria_bp)
    app.register_blueprint(claves_api_bp)
    app.register_blueprint(api_publica_bp)
    app.register_blueprint(notificaciones_bp)
    app.register_blueprint(reportes_personalizados_bp)
    app.register_blueprint(asistente_ia_bp)
    app.register_blueprint(importaciones_bp)
    app.register_blueprint(ayuda_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(alertas_bp)
    app.register_blueprint(reportes_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(configuracion_bp)
    app.register_blueprint(suscripciones_bp)
    app.register_blueprint(webhooks_pago_bp)
    app.register_blueprint(suite_comercial_bp)
    app.register_blueprint(integraciones_webhook_bp)
    app.register_blueprint(superadministracion_bp)
    app.register_blueprint(panel_superadministracion_bp)
    app.register_blueprint(panel_bp)

    def contexto_portada():
        planes = list(
            db.session.scalars(
                db.select(PlanSaaS)
                .where(
                    PlanSaaS.activo.is_(True),
                    PlanSaaS.codigo.in_(PLANES_PAGADOS_PUBLICOS),
                )
                .order_by(PlanSaaS.orden, PlanSaaS.id)
            )
        )
        return {
            "planes_publicos": planes,
            "formatear_clp": lambda valor: "$" + f"{int(valor):,}".replace(",", "."),
        }

    # Compatibilidad con las URLs históricas publicadas e indexadas. Se enlaza
    # directamente la misma vista para conservar también formularios POST.
    app.add_url_rule(
        "/login",
        endpoint="login_compatibilidad",
        view_func=app.view_functions["autenticacion.ingresar"],
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        "/registro",
        endpoint="registro_compatibilidad",
        view_func=app.view_functions["autenticacion.registro"],
        methods=["GET", "POST"],
    )

    @app.get("/")
    def inicio_publico():
        if not current_user.is_authenticated:
            return render_template("planes_publicos.html", **contexto_portada())

        if current_user.rol == "super_admin" and current_user.empresa_id is None:
            return redirect(url_for(("panel_superadministracion" ".inicio")))

        return redirect(url_for("panel.inicio"))

    @app.get("/planes")
    def planes_publicos():
        return render_template("planes_publicos.html", **contexto_portada())

    @app.route("/empresarial/solicitar", methods=["GET", "POST"])
    def solicitar_contrato_empresarial():
        enviado = False
        if request.method == "POST":
            datos = {
                clave: str(request.form.get(clave) or "").strip()
                for clave in ("empresa_nombre", "contacto_nombre", "email", "telefono", "mensaje")
            }
            if request.form.get("sitio_web"):
                return redirect(url_for("solicitar_contrato_empresarial", enviado="1"))
            if not datos["empresa_nombre"] or not datos["contacto_nombre"]:
                return (
                    render_template(
                        "contrato_empresarial.html",
                        error="Completa la empresa y la persona de contacto.",
                        datos=datos,
                    ),
                    400,
                )
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", datos["email"]):
                return (
                    render_template(
                        "contrato_empresarial.html",
                        error="Ingresa un correo válido.",
                        datos=datos,
                    ),
                    400,
                )
            try:
                productos = max(
                    0, min(int(request.form.get("productos_estimados") or 10000), 10**9)
                )
                usuarios = max(1, min(int(request.form.get("usuarios_estimados") or 12), 10**6))
            except ValueError:
                return (
                    render_template(
                        "contrato_empresarial.html",
                        error="Productos y usuarios deben ser números válidos.",
                        datos=datos,
                    ),
                    400,
                )
            solicitud = SolicitudContratoEmpresarial(
                empresa_nombre=datos["empresa_nombre"][:150],
                contacto_nombre=datos["contacto_nombre"][:150],
                email=datos["email"].lower()[:254],
                telefono=datos["telefono"][:30] or None,
                productos_estimados=productos,
                usuarios_estimados=usuarios,
                mensaje=datos["mensaje"][:3000] or None,
            )
            db.session.add(solicitud)
            db.session.commit()

            from .services.contratos_empresariales import (
                notificar_solicitud_empresarial,
            )

            notificar_solicitud_empresarial(solicitud)

            return redirect(
                url_for(
                    "solicitar_contrato_empresarial",
                    enviado="1",
                )
            )

        return render_template(
            "contrato_empresarial.html",
            enviado=enviado or request.args.get("enviado") == "1",
            datos={},
        )

    @app.get("/manifest.webmanifest")
    def manifiesto_web():
        return send_from_directory(app.static_folder, "manifest.webmanifest")

    @app.get("/service-worker.js")
    def service_worker():
        respuesta = make_response(send_from_directory(app.static_folder, "service-worker.js"))
        respuesta.headers["Service-Worker-Allowed"] = "/"
        respuesta.headers["Cache-Control"] = "no-cache"
        return respuesta

    from .commands import registrar_comandos

    registrar_comandos(app)

    @app.before_request
    def revalidar_contexto_guardado():
        from .services.contexto import CLAVE_BODEGA, CLAVE_SUCURSAL, obtener_contexto

        if (
            current_user.is_authenticated
            and current_user.rol != "super_admin"
            and (CLAVE_SUCURSAL in session or CLAVE_BODEGA in session)
        ):
            obtener_contexto(current_user, crear_automaticamente=False)

    @app.before_request
    def exigir_2fa_para_cuentas_privilegiadas():
        """Impide operar en producción hasta proteger cuentas administrativas."""
        if not app.config.get("REQUIRE_PRIVILEGED_2FA", False):
            return None
        if not current_user.is_authenticated or current_user.rol != "super_admin":
            return None
        if current_user.two_factor_enabled:
            return None
        permitidos = {
            "autenticacion.seguridad_cuenta",
            "autenticacion.salir",
            "autenticacion.reenviar_verificacion",
            "static",
        }
        if request.endpoint in permitidos:
            return None
        if request.path.startswith("/api/"):
            return (
                jsonify(
                    {
                        "codigo": "segundo_factor_requerido",
                        "mensaje": "Activa el segundo factor para continuar.",
                    }
                ),
                403,
            )
        return redirect(url_for("autenticacion.seguridad_cuenta"))

    @app.before_request
    def exigir_tarjeta_para_prueba():
        """La prueba comercial sólo opera después de autorizar el mandato."""
        if not app.config.get("REQUIRE_TRIAL_PAYMENT_METHOD", True):
            return None
        if (
            not current_user.is_authenticated
            or current_user.rol == "super_admin"
            or not current_user.empresa
        ):
            return None
        suscripcion = current_user.empresa.suscripcion_actual
        if not suscripcion:
            suscripcion = db.session.scalar(
                db.select(Suscripcion)
                .where(Suscripcion.empresa_id == current_user.empresa_id)
                .order_by(Suscripcion.id.desc())
                .limit(1)
            )
        if (
            not suscripcion
            or suscripcion.estado != "prueba"
            or suscripcion.metodo_pago_recurrente_estado == "activo"
        ):
            return None
        permitidos = {
            "panel.administracion_planes",
            "suscripciones.resumen",
            "suscripciones.iniciar_mandato_route",
            "autenticacion.salir",
            "autenticacion.seguridad_cuenta",
            "static",
        }
        if request.endpoint in permitidos:
            return None
        if request.path.startswith("/api/"):
            return (
                jsonify(
                    {
                        "codigo": "tarjeta_requerida",
                        "mensaje": "Autoriza una tarjeta para activar los 30 días de prueba.",
                    }
                ),
                402,
            )
        return redirect(url_for("panel.administracion_planes", tarjeta="requerida"))

    @app.errorhandler(403)
    def acceso_denegado(excepcion):
        return jsonify({"codigo": "acceso_denegado", "mensaje": excepcion.description}), 403

    @app.errorhandler(PermissionError)
    def operacion_fuera_de_ambito(excepcion):
        return jsonify({"codigo": "acceso_denegado", "mensaje": str(excepcion)}), 403

    return app


@login_manager.user_loader
def cargar_usuario(usuario_id: str):
    partes = usuario_id.split(":", 1)
    if len(partes) != 2 or not all(parte.isdigit() for parte in partes):
        return None
    usuario = db.session.get(Usuario, int(partes[0]))
    return usuario if usuario and usuario.version_sesion == int(partes[1]) else None
