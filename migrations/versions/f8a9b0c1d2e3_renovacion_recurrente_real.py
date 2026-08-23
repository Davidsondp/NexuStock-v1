"""Agrega estado operativo para cobros recurrentes y reintentos.

Revision ID: f8a9b0c1d2e3
Revises: f7a8b9c0d1e2
"""

from alembic import op
import sqlalchemy as sa

revision = "f8a9b0c1d2e3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("suscripcion") as batch_op:
        batch_op.add_column(sa.Column("fecha_proximo_cobro", sa.DateTime()))
        batch_op.add_column(
            sa.Column("intentos_cobro", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("proximo_reintento_en", sa.DateTime()))
        batch_op.add_column(sa.Column("ultimo_intento_cobro_en", sa.DateTime()))
        batch_op.add_column(sa.Column("ultimo_error_cobro", sa.String(length=500)))
        batch_op.add_column(sa.Column("ultimo_cobro_notificado_en", sa.DateTime()))
        batch_op.create_index("ix_suscripcion_fecha_proximo_cobro", ["fecha_proximo_cobro"])
        batch_op.create_index("ix_suscripcion_proximo_reintento_en", ["proximo_reintento_en"])


def downgrade():
    with op.batch_alter_table("suscripcion") as batch_op:
        batch_op.drop_index("ix_suscripcion_proximo_reintento_en")
        batch_op.drop_index("ix_suscripcion_fecha_proximo_cobro")
        batch_op.drop_column("ultimo_cobro_notificado_en")
        batch_op.drop_column("ultimo_error_cobro")
        batch_op.drop_column("ultimo_intento_cobro_en")
        batch_op.drop_column("proximo_reintento_en")
        batch_op.drop_column("intentos_cobro")
        batch_op.drop_column("fecha_proximo_cobro")
