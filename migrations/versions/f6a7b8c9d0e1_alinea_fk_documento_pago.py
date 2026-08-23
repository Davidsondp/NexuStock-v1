"""Alinea la clave de pago de documentos con el modelo.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    tipo_portable = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    with op.batch_alter_table("documento_facturacion_saas") as batch_op:
        batch_op.alter_column(
            "pago_id",
            existing_type=sa.BigInteger(),
            type_=tipo_portable,
            existing_nullable=False,
        )


def downgrade():
    tipo_portable = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    with op.batch_alter_table("documento_facturacion_saas") as batch_op:
        batch_op.alter_column(
            "pago_id",
            existing_type=tipo_portable,
            type_=sa.BigInteger(),
            existing_nullable=False,
        )
