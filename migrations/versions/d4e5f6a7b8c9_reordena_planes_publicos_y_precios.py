"""Reordena la oferta pública y actualiza los precios comerciales.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

from alembic import op


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE plan_saas SET nombre='Prueba gratuita', "
        "descripcion='Prueba gratuita con funciones profesionales' "
        "WHERE codigo='prueba'"
    )
    op.execute(
        "UPDATE plan_saas SET nombre='Base gratuita', "
        "descripcion='Continuidad básica después de la prueba' "
        "WHERE codigo='basico'"
    )
    op.execute(
        "UPDATE plan_saas SET precio_mensual=9990, precio_anual=99900 "
        "WHERE codigo='avanzado'"
    )
    op.execute(
        "UPDATE plan_saas SET precio_mensual=14990, precio_anual=149900 "
        "WHERE codigo='ultra'"
    )
    op.execute(
        "UPDATE plan_saas SET precio_mensual=19990, precio_anual=199900 "
        "WHERE codigo='profesional'"
    )
    op.execute(
        "UPDATE plan_saas SET nombre='Empresarial', precio_mensual=49990, "
        "precio_anual=499900 "
        "WHERE codigo='empresa'"
    )


def downgrade():
    op.execute(
        "UPDATE plan_saas SET nombre='Prueba', "
        "descripcion='Prueba con funciones profesionales' WHERE codigo='prueba'"
    )
    op.execute(
        "UPDATE plan_saas SET nombre='Inicial', "
        "descripcion='Plan gratuito para comenzar' WHERE codigo='basico'"
    )
    op.execute(
        "UPDATE plan_saas SET precio_mensual=9990, precio_anual=99900 "
        "WHERE codigo='avanzado'"
    )
    op.execute(
        "UPDATE plan_saas SET precio_mensual=14990, precio_anual=149900 "
        "WHERE codigo='ultra'"
    )
    op.execute(
        "UPDATE plan_saas SET precio_mensual=19990, precio_anual=199900 "
        "WHERE codigo='profesional'"
    )
    op.execute(
        "UPDATE plan_saas SET nombre='Enterprise', precio_mensual=49990, "
        "precio_anual=499900 "
        "WHERE codigo='empresa'"
    )
