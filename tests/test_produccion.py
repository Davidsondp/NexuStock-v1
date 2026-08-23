from sqlalchemy import text

from app.commands import errores_integraciones_produccion
from app.models import db
from config import normalizar_url_base_datos
from pathlib import Path


def test_normaliza_urls_postgresql_para_psycopg3():
    assert normalizar_url_base_datos("postgres://u:c@host/base") == (
        "postgresql+psycopg://u:c@host/base"
    )
    assert normalizar_url_base_datos("postgresql://u:c@host/base") == (
        "postgresql+psycopg://u:c@host/base"
    )


def test_estado_preparacion_confirma_base_de_datos(client):
    respuesta = client.get("/estado/preparacion")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"estado": "preparado", "servicio": "nexustock"}


def test_verificar_produccion_exige_revision_alembic(app):
    corredor = app.test_cli_runner()
    resultado = corredor.invoke(args=["verificar-produccion"])
    assert resultado.exit_code != 0
    assert "migración" in resultado.output


def test_verificar_produccion_con_revision_y_planes(app):
    with app.app_context():
        db.session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        db.session.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('revision-prueba')")
        )
        db.session.commit()
    siembra = app.test_cli_runner().invoke(args=["seed-planes"])
    assert siembra.exit_code == 0
    resultado = app.test_cli_runner().invoke(args=["verificar-produccion"])
    assert resultado.exit_code == 0
    assert "Producción verificada" in resultado.output


def test_render_declara_configuracion_webpay_completa():
    contenido = Path("render.yaml").read_text(encoding="utf-8-sig")

    for variable in (
        "BASE_URL",
        "WEBPAY_COMMERCE_CODE",
        "WEBPAY_API_KEY",
        "WEBPAY_ONECLICK_PARENT_COMMERCE_CODE",
        "WEBPAY_ONECLICK_CHILD_COMMERCE_CODE",
        "WEBPAY_ONECLICK_API_KEY",
        "WEBPAY_ENV",
        "MERCADOPAGO_ACCESS_TOKEN",
        "MERCADOPAGO_WEBHOOK_SECRET",
        "MERCADOPAGO_ENV",
    ):
        assert f"- key: {variable}" in contenido

    assert "value: production" in contenido


def test_verificacion_estricta_exige_integraciones_comerciales():
    errores = errores_integraciones_produccion({})
    for variable in (
        "BASE_URL",
        "WEBPAY_COMMERCE_CODE",
        "WEBPAY_API_KEY",
        "WEBPAY_ONECLICK_PARENT_COMMERCE_CODE",
        "MERCADOPAGO_ACCESS_TOKEN",
        "MERCADOPAGO_WEBHOOK_SECRET",
        "OPENAI_API_KEY",
    ):
        assert any(variable in error for error in errores)


def test_verificacion_estricta_acepta_configuracion_completa():
    configuracion = {
        "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://nexustock@db/nexustock",
        "BASE_URL": "https://www.nexustock.cl",
        "WEBPAY_ENV": "production",
        "WEBPAY_COMMERCE_CODE": "codigo",
        "WEBPAY_API_KEY": "secreto",
        "WEBPAY_ONECLICK_PARENT_COMMERCE_CODE": "padre",
        "WEBPAY_ONECLICK_CHILD_COMMERCE_CODE": "hijo",
        "WEBPAY_ONECLICK_API_KEY": "secreto-oneclick",
        "MERCADOPAGO_ENV": "production",
        "MERCADOPAGO_ACCESS_TOKEN": "token",
        "MERCADOPAGO_WEBHOOK_SECRET": "firma",
        "DTE_PROVIDER_URL": "https://api.proveedor-certificado.cl",
        "DTE_API_KEY": "clave-dte",
        "OPENAI_API_KEY": "clave",
        "REQUIRE_PRIVILEGED_2FA": True,
        "PASSWORD_MIN_LENGTH": 12,
    }
    assert errores_integraciones_produccion(configuracion) == []
