"""Finanzas recurrentes y metadatos de planes empresariales.

Revision ID: a1b2c3d4e5f6
Revises: e6f7a8b9c0d1
"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("plan_saas") as batch:
        batch.add_column(sa.Column("nivel_comercial", sa.String(length=20), nullable=False,
                                   server_default="inicio"))
        batch.add_column(sa.Column("soporte", sa.String(length=30), nullable=False,
                                   server_default="estandar"))
        batch.create_index("ix_plan_saas_nivel_comercial", ["nivel_comercial"])
    with op.batch_alter_table("suscripcion") as batch:
        batch.add_column(sa.Column("renovacion_automatica", sa.Boolean(), nullable=False,
                                   server_default=sa.true()))
        batch.add_column(sa.Column("cancelar_al_fin_periodo", sa.Boolean(), nullable=False,
                                   server_default=sa.false()))
        batch.add_column(sa.Column("periodo_actual_inicio", sa.DateTime()))
        batch.add_column(sa.Column("periodo_actual_fin", sa.DateTime()))
        batch.add_column(sa.Column("gracia_hasta", sa.DateTime()))
        batch.add_column(sa.Column("proveedor_cobro", sa.String(length=30)))
    op.execute(
        "UPDATE suscripcion SET periodo_actual_inicio = fecha_inicio, "
        "periodo_actual_fin = fecha_fin"
    )


def downgrade():
    with op.batch_alter_table("suscripcion") as batch:
        batch.drop_column("proveedor_cobro")
        batch.drop_column("gracia_hasta")
        batch.drop_column("periodo_actual_fin")
        batch.drop_column("periodo_actual_inicio")
        batch.drop_column("cancelar_al_fin_periodo")
        batch.drop_column("renovacion_automatica")
    with op.batch_alter_table("plan_saas") as batch:
        batch.drop_index("ix_plan_saas_nivel_comercial")
        batch.drop_column("soporte")
        batch.drop_column("nivel_comercial")
