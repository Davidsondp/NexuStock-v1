import click
from flask import current_app
from sqlalchemy import text

from .models import PlanSaaS, Usuario, db
from .services.planes import funciones_plan

PLANES = (
    dict(
        codigo="prueba",
        nombre="Prueba heredada",
        descripcion="Compatibilidad histórica; la prueba ahora pertenece al plan elegido",
        precio_mensual=0,
        precio_anual=0,
        dias_prueba=30,
        limite_productos=500,
        limite_usuarios=2,
        limite_movimientos_mes=500,
        limite_sucursales=1,
        limite_bodegas=1,
        almacenamiento_mb=500,
        funciones=funciones_plan("prueba"),
        nivel_comercial="prueba",
        soporte="estandar",
        orden=1,
        activo=False,
    ),
    dict(
        codigo="basico",
        nombre="Base gratuita",
        descripcion="Compatibilidad interna para cuentas heredadas; no se asigna automáticamente",
        precio_mensual=0,
        precio_anual=0,
        dias_prueba=0,
        limite_productos=100,
        limite_usuarios=1,
        limite_movimientos_mes=1000,
        limite_sucursales=1,
        limite_bodegas=1,
        almacenamiento_mb=2000,
        funciones=funciones_plan("basico"),
        nivel_comercial="inicio",
        soporte="email",
        orden=2,
        activo=False,
    ),
    dict(
        codigo="avanzado",
        nombre="Avanzado",
        descripcion="Colaboración y control para pequeños equipos",
        precio_mensual=9990,
        precio_anual=99900,
        dias_prueba=30,
        limite_productos=500,
        limite_usuarios=2,
        limite_movimientos_mes=5000,
        limite_sucursales=1,
        limite_bodegas=1,
        almacenamiento_mb=2000,
        funciones=funciones_plan("avanzado"),
        nivel_comercial="avanzado",
        soporte="email",
        orden=3,
    ),
    dict(
        codigo="ultra",
        nombre="Ultra",
        descripcion="Operación diaria con compras y control avanzado",
        precio_mensual=14990,
        precio_anual=149900,
        dias_prueba=30,
        limite_productos=2000,
        limite_usuarios=5,
        limite_movimientos_mes=20000,
        limite_sucursales=2,
        limite_bodegas=3,
        almacenamiento_mb=5000,
        funciones=funciones_plan("ultra"),
        nivel_comercial="ultra",
        soporte="prioritario",
        orden=4,
    ),
    dict(
        codigo="profesional",
        nombre="Profesional",
        descripcion="Operación y control avanzado",
        precio_mensual=19990,
        precio_anual=199900,
        dias_prueba=30,
        limite_productos=5000,
        limite_usuarios=10,
        limite_movimientos_mes=50000,
        limite_sucursales=3,
        limite_bodegas=3,
        almacenamiento_mb=5000,
        funciones=funciones_plan("profesional"),
        nivel_comercial="premium",
        soporte="prioritario",
        orden=5,
    ),
    dict(
        codigo="empresa",
        nombre="Empresarial",
        descripcion="Control empresarial para organizaciones de gran escala",
        precio_mensual=49990,
        precio_anual=499900,
        dias_prueba=30,
        limite_productos=10000,
        limite_usuarios=12,
        limite_movimientos_mes=None,
        limite_sucursales=None,
        limite_bodegas=None,
        almacenamiento_mb=20000,
        funciones=funciones_plan("empresa"),
        nivel_comercial="empresa",
        soporte="dedicado",
        orden=6,
    ),
    dict(
        codigo="corporativo",
        nombre="Corporativo",
        descripcion="Gobierno, seguridad y escala para grandes organizaciones",
        precio_mensual=0,
        precio_anual=0,
        dias_prueba=0,
        limite_productos=None,
        limite_usuarios=None,
        limite_movimientos_mes=None,
        limite_sucursales=None,
        limite_bodegas=None,
        almacenamiento_mb=None,
        funciones=funciones_plan("corporativo"),
        nivel_comercial="corporativo",
        soporte="acuerdo_servicio",
        orden=7,
        activo=False,
    ),
)


def errores_integraciones_produccion(configuracion):
    """Devuelve configuraciones que impedirían vender el servicio completo."""
    errores = []
    base_datos = str(configuracion.get("SQLALCHEMY_DATABASE_URI") or "")
    if not base_datos.startswith(("postgresql://", "postgresql+psycopg://")):
        errores.append("DATABASE_URL debe apuntar a PostgreSQL")
    base_url = str(configuracion.get("BASE_URL") or "")
    if not base_url.startswith("https://"):
        errores.append("BASE_URL debe ser una URL HTTPS")
    mercado_pago_completo = all(
        (
            configuracion.get("MERCADOPAGO_ENV") == "production",
            configuracion.get("MERCADOPAGO_ACCESS_TOKEN"),
            configuracion.get("MERCADOPAGO_WEBHOOK_SECRET"),
        )
    )

    webpay_oneclick_completo = all(
        (
            configuracion.get("WEBPAY_ONECLICK_ENV") == "production",
            configuracion.get("WEBPAY_ONECLICK_PARENT_COMMERCE_CODE"),
            configuracion.get("WEBPAY_ONECLICK_CHILD_COMMERCE_CODE"),
            configuracion.get("WEBPAY_ONECLICK_API_KEY"),
        )
    )

    if not mercado_pago_completo and not webpay_oneclick_completo:
        errores.append(
            "debe configurarse Mercado Pago Suscripciones "
            "o Webpay Oneclick productivo"
        )
    if not str(configuracion.get("DTE_PROVIDER_URL") or "").startswith("https://"):
        errores.append("DTE_PROVIDER_URL debe ser HTTPS")
    if not configuracion.get("DTE_API_KEY"):
        errores.append("falta DTE_API_KEY")
    if not configuracion.get("OPENAI_API_KEY"):
        errores.append("falta OPENAI_API_KEY")
    if not configuracion.get("REQUIRE_PRIVILEGED_2FA"):
        errores.append("REQUIRE_PRIVILEGED_2FA debe estar activo")
    if int(configuracion.get("PASSWORD_MIN_LENGTH", 0)) < 12:
        errores.append("PASSWORD_MIN_LENGTH debe ser al menos 12")
    return errores


def registrar_comandos(app):
    @app.cli.command("conciliar-pagos")
    @click.option("--limite", type=click.IntRange(1, 1000), default=200)
    def conciliar_pagos(limite):
        """Consulta al proveedor los cobros iniciados o procesando."""
        from .services.conciliacion_pagos import conciliar_pagos_pendientes

        resultado = conciliar_pagos_pendientes(configuracion=current_app.config, limite=limite)
        click.echo(
            "Conciliación terminada: "
            + ", ".join(f"{clave}={valor}" for clave, valor in resultado.items())
        )

    @app.cli.command("renovar-suscripciones")
    @click.option("--limite", type=click.IntRange(1, 1000), default=200)
    def renovar_suscripciones(limite):
        """Cobra mandatos vencidos, reintenta rechazos y envía avisos."""
        from .services.pagos_recurrentes import procesar_renovaciones

        resultado = procesar_renovaciones(
            configuracion=current_app.config,
            limite=limite,
        )
        click.echo(
            "Renovaciones terminadas: "
            + ", ".join(f"{clave}={valor}" for clave, valor in resultado.items())
        )

    @app.cli.command("verificar-produccion")
    def verificar_produccion():
        """Comprueba conexión, migración aplicada y datos esenciales."""
        try:
            db.session.execute(text("SELECT 1"))
            revision = db.session.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
        except Exception as exc:
            db.session.rollback()
            raise click.ClickException(
                "No fue posible verificar la base de datos o su migración"
            ) from exc
        if not revision:
            raise click.ClickException("La base de datos no tiene una revisión de Alembic aplicada")
        codigos = set(db.session.scalars(db.select(PlanSaaS.codigo)))
        faltantes = {datos["codigo"] for datos in PLANES} - codigos
        if faltantes:
            raise click.ClickException("Faltan planes oficiales: " + ", ".join(sorted(faltantes)))
        if not current_app.testing:
            errores = errores_integraciones_produccion(current_app.config)
            if errores:
                raise click.ClickException(
                    "Integraciones productivas incompletas: " + "; ".join(errores)
                )
        click.echo(f"Producción verificada. Revisión de base de datos: {revision}")

    @app.cli.command("seed-planes")
    def seed_planes():
        """Sincroniza el catálogo oficial sin alterar suscripciones históricas."""
        for datos in PLANES:
            plan = db.session.scalar(db.select(PlanSaaS).where(PlanSaaS.codigo == datos["codigo"]))
            if plan is None:
                db.session.add(PlanSaaS(**datos))
            else:
                funciones = dict(plan.funciones or {})
                for codigo, incluida in datos["funciones"].items():
                    funciones.setdefault(codigo, incluida)
                plan.funciones = funciones
                plan.dias_prueba = datos["dias_prueba"]
                if plan.codigo in {"prueba", "basico", "corporativo"}:
                    plan.activo = False
        db.session.commit()
        click.echo("Planes y capacidades faltantes configurados; ediciones existentes preservadas.")

    @app.cli.command("crear-super-admin")
    @click.option("--nombre", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option(confirmation_prompt=True)
    def crear_super_admin(nombre, email, password):
        """Crea una cuenta global fuera de cualquier empresa."""
        email = email.strip().lower()
        if db.session.scalar(db.select(Usuario.id).where(Usuario.email == email)):
            raise click.ClickException("El correo ya está registrado")
        try:
            usuario = Usuario(
                empresa_id=None,
                nombre=nombre.strip(),
                email=email,
                rol="super_admin",
                activo=True,
                email_verificado=True,
            )
            usuario.set_password(password)
            db.session.add(usuario)
            db.session.commit()
            click.echo("Super Admin creado correctamente.")
        except Exception as exc:
            db.session.rollback()
            raise click.ClickException(str(exc)) from exc

    @app.cli.command("generar-alertas")
    def generar_alertas():
        """Genera alertas para todas las empresas activas."""
        from .models import Empresa
        from .services.alertas import (
            ServicioAlertas,
        )

        empresa_ids = list(
            db.session.scalars(
                db.select(Empresa.id)
                .where(
                    Empresa.estado == "activa",
                    Empresa.eliminado.is_(False),
                )
                .order_by(Empresa.id)
            )
        )

        procesadas = 0
        omitidas = 0
        errores = 0
        creadas = 0
        actualizadas = 0
        resueltas = 0

        for empresa_id in empresa_ids:
            usuario = db.session.scalar(
                db.select(Usuario)
                .where(
                    Usuario.empresa_id == empresa_id,
                    Usuario.rol.in_(
                        {
                            "jefe",
                            "supervisor",
                        }
                    ),
                    Usuario.activo.is_(True),
                    Usuario.eliminado.is_(False),
                )
                .order_by(
                    (Usuario.rol == "jefe").desc(),
                    Usuario.id,
                )
            )

            if usuario is None:
                omitidas += 1
                click.echo(
                    (
                        f"Empresa {empresa_id} omitida: "
                        "no posee una jefatura "
                        "o supervisor activo."
                    ),
                    err=True,
                )
                continue

            try:
                resultado = ServicioAlertas(usuario).generar()

                creadas += resultado.creadas
                actualizadas += resultado.actualizadas
                resueltas += resultado.resueltas
                procesadas += 1
            except Exception as exc:
                db.session.rollback()
                errores += 1
                click.echo(
                    (f"Error en empresa " f"{empresa_id}: {exc}"),
                    err=True,
                )
            finally:
                db.session.remove()

        click.echo(f"Empresas procesadas: {procesadas}")
        click.echo(f"Empresas omitidas: {omitidas}")
        click.echo(f"Alertas creadas: {creadas}")
        click.echo(f"Alertas actualizadas: {actualizadas}")
        click.echo(f"Alertas resueltas: {resueltas}")
        click.echo(f"Errores: {errores}")

        if errores:
            raise click.ClickException(
                ("La generación terminó con " f"{errores} empresa(s) fallida(s).")
            )

    @app.cli.command("capturar-inventario")
    def capturar_inventario():
        """Captura un snapshot diario idempotente del inventario."""
        from .services.reportes_personalizados import capturar_snapshot_inventario

        creados = capturar_snapshot_inventario()
        click.echo(f"Snapshots creados: {creados}")
