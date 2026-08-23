"""Agrega reportes personalizados y snapshots de inventario.

Revision ID: d62f04ae9130
Revises: c84b10e77231
"""

from alembic import op
import sqlalchemy as sa

revision = "d62f04ae9130"
down_revision = "c84b10e77231"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.add_column(sa.Column("token_verificacion_hash", sa.String(64)))
        batch_op.add_column(sa.Column("token_verificacion_expira", sa.DateTime()))
        batch_op.create_unique_constraint(
            "uq_usuario_token_verificacion_hash", ["token_verificacion_hash"]
        )
        batch_op.create_index("ix_usuario_token_verificacion_hash", ["token_verificacion_hash"])
    op.create_table(
        "snapshot_inventario",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("bodega_id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("cantidad", sa.Numeric(14, 3), nullable=False),
        sa.Column("cantidad_reservada", sa.Numeric(14, 3), nullable=False),
        sa.Column("costo_promedio", sa.Numeric(14, 4), nullable=False),
        sa.Column("capturado_en", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["producto_id", "empresa_id"], ["producto.id", "producto.empresa_id"]
        ),
        sa.ForeignKeyConstraint(["bodega_id", "empresa_id"], ["bodega.id", "bodega.empresa_id"]),
        sa.UniqueConstraint(
            "empresa_id", "producto_id", "bodega_id", "fecha", name="uq_snapshot_inventario_dia"
        ),
    )
    op.create_index("ix_snapshot_empresa_fecha", "snapshot_inventario", ["empresa_id", "fecha"])
    op.create_table(
        "reporte_personalizado",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("creado_por_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("configuracion", sa.JSON(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("eliminado", sa.Boolean(), nullable=False),
        sa.Column("eliminado_en", sa.DateTime()),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["creado_por_id", "empresa_id"], ["usuario.id", "usuario.empresa_id"]
        ),
        sa.UniqueConstraint("empresa_id", "nombre", name="uq_reporte_personalizado_nombre"),
    )
    op.create_index("ix_reporte_personalizado_empresa_id", "reporte_personalizado", ["empresa_id"])


def downgrade():
    op.drop_index("ix_reporte_personalizado_empresa_id", table_name="reporte_personalizado")
    op.drop_table("reporte_personalizado")
    op.drop_index("ix_snapshot_empresa_fecha", table_name="snapshot_inventario")
    op.drop_table("snapshot_inventario")
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.drop_index("ix_usuario_token_verificacion_hash")
        batch_op.drop_constraint("uq_usuario_token_verificacion_hash", type_="unique")
        batch_op.drop_column("token_verificacion_expira")
        batch_op.drop_column("token_verificacion_hash")
