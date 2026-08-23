"""refuerza identidad financiera y progreso WMS

Revision ID: d5e6f7a8b9c0
Revises: c4c508486ee1
"""

from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "c4c508486ee1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("pago") as batch_op:
        batch_op.add_column(sa.Column("token_proveedor", sa.String(length=180), nullable=True))
        batch_op.add_column(sa.Column("transaccion_proveedor_id", sa.String(length=180), nullable=True))
        batch_op.create_unique_constraint("uq_pago_token_proveedor", ["proveedor", "token_proveedor"])
        batch_op.create_unique_constraint(
            "uq_pago_transaccion_proveedor", ["proveedor", "transaccion_proveedor_id"]
        )
    with op.batch_alter_table("orden_wms") as batch_op:
        batch_op.add_column(sa.Column("progreso", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    with op.batch_alter_table("orden_wms") as batch_op:
        batch_op.drop_column("progreso")
    with op.batch_alter_table("pago") as batch_op:
        batch_op.drop_constraint("uq_pago_transaccion_proveedor", type_="unique")
        batch_op.drop_constraint("uq_pago_token_proveedor", type_="unique")
        batch_op.drop_column("transaccion_proveedor_id")
        batch_op.drop_column("token_proveedor")
