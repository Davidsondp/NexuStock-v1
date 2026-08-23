"""Asocia seriales a líneas de venta.

Revision ID: c84b10e77231
Revises: ab7ae6131661
"""

from alembic import op
import sqlalchemy as sa

revision = "c84b10e77231"
down_revision = "ab7ae6131661"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("venta_item") as batch_op:
        batch_op.create_unique_constraint("uq_venta_item_id_empresa", ["id", "empresa_id"])
    with op.batch_alter_table("producto_serial") as batch_op:
        batch_op.add_column(sa.Column("venta_item_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("transferencia_item_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_producto_serial_venta_item_id", ["venta_item_id"])
        batch_op.create_index("ix_producto_serial_transferencia_item_id", ["transferencia_item_id"])
        batch_op.create_foreign_key(
            "fk_serial_venta_item_empresa",
            "venta_item",
            ["venta_item_id", "empresa_id"],
            ["id", "empresa_id"],
        )
    with op.batch_alter_table("transferencia_item") as batch_op:
        batch_op.create_unique_constraint("uq_transferencia_item_id_empresa", ["id", "empresa_id"])
    with op.batch_alter_table("producto_serial") as batch_op:
        batch_op.create_foreign_key(
            "fk_serial_transferencia_item_empresa",
            "transferencia_item",
            ["transferencia_item_id", "empresa_id"],
            ["id", "empresa_id"],
        )


def downgrade():
    with op.batch_alter_table("producto_serial") as batch_op:
        batch_op.drop_constraint("fk_serial_transferencia_item_empresa", type_="foreignkey")
        batch_op.drop_constraint("fk_serial_venta_item_empresa", type_="foreignkey")
        batch_op.drop_index("ix_producto_serial_transferencia_item_id")
        batch_op.drop_index("ix_producto_serial_venta_item_id")
        batch_op.drop_column("transferencia_item_id")
        batch_op.drop_column("venta_item_id")
    with op.batch_alter_table("transferencia_item") as batch_op:
        batch_op.drop_constraint("uq_transferencia_item_id_empresa", type_="unique")
    with op.batch_alter_table("venta_item") as batch_op:
        batch_op.drop_constraint("uq_venta_item_id_empresa", type_="unique")
