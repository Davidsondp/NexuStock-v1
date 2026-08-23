"""Alinea índices de verificación y reportes con los modelos.

Revision ID: f4c8a1b2d3e4
Revises: e31a84c0f5b2
"""

from alembic import op

revision = "f4c8a1b2d3e4"
down_revision = "e31a84c0f5b2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_reporte_personalizado_eliminado",
        "reporte_personalizado",
        ["eliminado"],
    )
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.drop_index("ix_usuario_token_verificacion_hash")
        batch_op.drop_constraint(
            "uq_usuario_token_verificacion_hash",
            type_="unique",
        )
        batch_op.create_index(
            "ix_usuario_token_verificacion_hash",
            ["token_verificacion_hash"],
            unique=True,
        )


def downgrade():
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.drop_index("ix_usuario_token_verificacion_hash")
        batch_op.create_unique_constraint(
            "uq_usuario_token_verificacion_hash",
            ["token_verificacion_hash"],
        )
        batch_op.create_index(
            "ix_usuario_token_verificacion_hash",
            ["token_verificacion_hash"],
        )
    op.drop_index(
        "ix_reporte_personalizado_eliminado",
        table_name="reporte_personalizado",
    )
