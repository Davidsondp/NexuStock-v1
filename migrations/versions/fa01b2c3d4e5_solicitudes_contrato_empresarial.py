"""Solicitudes de contrato Empresarial separadas del checkout.

Revision ID: fa01b2c3d4e5
Revises: f9b0c1d2e3f4
"""

import sqlalchemy as sa
from alembic import op

revision = "fa01b2c3d4e5"
down_revision = "f9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "solicitud_contrato_empresarial",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_nombre", sa.String(length=150), nullable=False),
        sa.Column("contacto_nombre", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.Column("productos_estimados", sa.Integer(), nullable=False),
        sa.Column("usuarios_estimados", sa.Integer(), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("observacion_interna", sa.Text(), nullable=True),
        sa.Column("atendida_en", sa.DateTime(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "estado IN ('nueva','contactada','cotizada','contratada','descartada')",
            name="ck_solicitud_contrato_estado",
        ),
        sa.CheckConstraint("productos_estimados >= 0", name="ck_contrato_productos_estimados"),
        sa.CheckConstraint("usuarios_estimados >= 1", name="ck_contrato_usuarios_estimados"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_solicitud_contrato_empresarial_email",
        "solicitud_contrato_empresarial",
        ["email"],
    )
    op.create_index(
        "ix_solicitud_contrato_empresarial_estado",
        "solicitud_contrato_empresarial",
        ["estado"],
    )
    op.create_index(
        "ix_solicitud_contrato_estado_fecha",
        "solicitud_contrato_empresarial",
        ["estado", "creado_en"],
    )


def downgrade():
    op.drop_index(
        "ix_solicitud_contrato_estado_fecha",
        table_name="solicitud_contrato_empresarial",
    )
    op.drop_index(
        "ix_solicitud_contrato_empresarial_estado",
        table_name="solicitud_contrato_empresarial",
    )
    op.drop_index(
        "ix_solicitud_contrato_empresarial_email",
        table_name="solicitud_contrato_empresarial",
    )
    op.drop_table("solicitud_contrato_empresarial")
