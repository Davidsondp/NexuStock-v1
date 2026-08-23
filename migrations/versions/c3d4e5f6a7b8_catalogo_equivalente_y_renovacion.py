"""Catálogo equivalente y estado seguro de renovación recurrente.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("suscripcion") as batch:
        batch.add_column(sa.Column(
            "metodo_pago_recurrente_estado", sa.String(length=20), nullable=False,
            server_default="no_requerido",
        ))
        batch.add_column(sa.Column("referencia_metodo_pago", sa.String(length=180)))
        batch.create_check_constraint(
            "ck_suscripcion_metodo_recurrente_estado",
            "metodo_pago_recurrente_estado IN "
            "('no_requerido','pendiente','activo','revocado','fallido')",
        )
    op.execute(
        "UPDATE plan_saas SET limite_productos=500, limite_usuarios=2 "
        "WHERE codigo='prueba'"
    )
    op.execute(
        "UPDATE plan_saas SET descripcion='Colaboración y control para pequeños equipos', "
        "precio_mensual=9990, precio_anual=99900, limite_productos=500, "
        "limite_usuarios=2, limite_movimientos_mes=5000, limite_sucursales=1, "
        "limite_bodegas=1, almacenamiento_mb=2000, nivel_comercial='avanzado', "
        "orden=3 WHERE codigo='avanzado'"
    )
    op.execute("UPDATE plan_saas SET orden=5 WHERE codigo='profesional'")
    op.execute("UPDATE plan_saas SET orden=6 WHERE codigo='empresa'")
    op.execute("UPDATE plan_saas SET orden=7 WHERE codigo='corporativo'")


def downgrade():
    op.execute(
        "UPDATE plan_saas SET limite_productos=100, limite_usuarios=2 "
        "WHERE codigo='prueba'"
    )
    op.execute(
        "UPDATE plan_saas SET descripcion='Control colaborativo para negocios en crecimiento', "
        "precio_mensual=14990, precio_anual=149900, limite_productos=2000, "
        "limite_usuarios=5, limite_movimientos_mes=20000, limite_sucursales=2, "
        "limite_bodegas=3, almacenamiento_mb=5000, orden=3 WHERE codigo='avanzado'"
    )
    op.execute("UPDATE plan_saas SET orden=4 WHERE codigo='profesional'")
    op.execute("UPDATE plan_saas SET orden=5 WHERE codigo='empresa'")
    op.execute("UPDATE plan_saas SET orden=6 WHERE codigo='corporativo'")
    with op.batch_alter_table("suscripcion") as batch:
        batch.drop_constraint("ck_suscripcion_metodo_recurrente_estado", type_="check")
        batch.drop_column("referencia_metodo_pago")
        batch.drop_column("metodo_pago_recurrente_estado")
