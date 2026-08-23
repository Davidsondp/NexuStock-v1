"""Comprobaciones que sólo se ejecutan contra PostgreSQL real en CI."""

import os

import pytest
from sqlalchemy import create_engine, inspect, text

from config import normalizar_url_base_datos

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL no configurada")


@pytest.fixture(scope="module")
def motor():
    engine = create_engine(normalizar_url_base_datos(URL), pool_pre_ping=True)
    yield engine
    engine.dispose()


def test_postgresql_tiene_migracion_actual(motor):
    with motor.connect() as conexion:
        revision = conexion.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision == "ab7ae6131661"


def test_postgresql_contiene_esquema_multiempresa(motor):
    inspector = inspect(motor)
    tablas = set(inspector.get_table_names())
    assert {"empresa", "usuario", "producto", "inventario", "movimiento", "pago"} <= tablas
    indices = {indice["name"] for indice in inspector.get_indexes("suscripcion")}
    assert "uq_suscripcion_empresa_vigente" in indices


def test_postgresql_admite_bloqueo_para_actualizacion(motor):
    with motor.begin() as conexion:
        conexion.execute(text("SELECT id FROM empresa ORDER BY id LIMIT 1 FOR UPDATE"))
