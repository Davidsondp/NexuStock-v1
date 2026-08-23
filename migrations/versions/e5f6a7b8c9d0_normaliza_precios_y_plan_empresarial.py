"""Normaliza precios públicos y traduce el plan Empresarial.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""

from alembic import op


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
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
        "precio_anual=499900 WHERE codigo='empresa'"
    )


def downgrade():
    op.execute(
        "UPDATE plan_saas SET precio_mensual=29990, precio_anual=299900 "
        "WHERE codigo='avanzado'"
    )
    op.execute(
        "UPDATE plan_saas SET precio_mensual=59990, precio_anual=599900 "
        "WHERE codigo='ultra'"
    )
    op.execute(
        "UPDATE plan_saas SET precio_mensual=149990, precio_anual=1499900 "
        "WHERE codigo='profesional'"
    )
    op.execute(
        "UPDATE plan_saas SET nombre='Enterprise', precio_mensual=0, "
        "precio_anual=0 WHERE codigo='empresa'"
    )
