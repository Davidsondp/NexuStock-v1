"""Agrega campos personalizados seguros al catálogo.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
"""

from alembic import op
import sqlalchemy as sa

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("producto") as batch_op:
        batch_op.add_column(
            sa.Column("campos_personalizados", sa.JSON(), nullable=True)
        )
    op.execute("UPDATE producto SET campos_personalizados = '{}' WHERE campos_personalizados IS NULL")
    with op.batch_alter_table("producto") as batch_op:
        batch_op.alter_column("campos_personalizados", nullable=False)


def downgrade():
    with op.batch_alter_table("producto") as batch_op:
        batch_op.drop_column("campos_personalizados")
