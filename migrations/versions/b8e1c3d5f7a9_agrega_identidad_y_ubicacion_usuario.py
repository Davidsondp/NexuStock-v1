"""Agrega identidad y ubicación consentida de usuarios.

Revision ID: b8e1c3d5f7a9
Revises: a7d9e2f4b6c8
"""

from alembic import op
import sqlalchemy as sa

revision = "b8e1c3d5f7a9"
down_revision = "a7d9e2f4b6c8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuario") as batch:
        batch.add_column(sa.Column("identificacion_fiscal", sa.String(30), nullable=True))
        batch.add_column(sa.Column("telefono", sa.String(30), nullable=True))
        batch.add_column(
            sa.Column(
                "ubicacion_consentida", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch.add_column(sa.Column("ultima_latitud", sa.Numeric(9, 6), nullable=True))
        batch.add_column(sa.Column("ultima_longitud", sa.Numeric(9, 6), nullable=True))
        batch.add_column(sa.Column("ultima_precision_m", sa.Numeric(10, 2), nullable=True))
        batch.add_column(sa.Column("ubicacion_actualizada_en", sa.DateTime(), nullable=True))
        batch.create_index(
            "ix_usuario_identificacion_fiscal", ["identificacion_fiscal"], unique=True
        )
        batch.create_index(
            "ix_usuario_ubicacion_actualizada_en", ["ubicacion_actualizada_en"], unique=False
        )


def downgrade():
    with op.batch_alter_table("usuario") as batch:
        batch.drop_index("ix_usuario_ubicacion_actualizada_en")
        batch.drop_index("ix_usuario_identificacion_fiscal")
        for columna in (
            "ubicacion_actualizada_en",
            "ultima_precision_m",
            "ultima_longitud",
            "ultima_latitud",
            "ubicacion_consentida",
            "telefono",
            "identificacion_fiscal",
        ):
            batch.drop_column(columna)
