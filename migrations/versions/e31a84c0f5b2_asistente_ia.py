"""Agrega interacciones del asistente IA.

Revision ID: e31a84c0f5b2
Revises: d62f04ae9130
"""

from alembic import op
import sqlalchemy as sa

revision = "e31a84c0f5b2"
down_revision = "d62f04ae9130"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interaccion_ia",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("conversacion_id", sa.String(36), nullable=False),
        sa.Column("modo", sa.String(30), nullable=False),
        sa.Column("pregunta", sa.Text(), nullable=False),
        sa.Column("respuesta", sa.JSON(), nullable=False),
        sa.Column("proveedor", sa.String(30), nullable=False),
        sa.Column("modelo", sa.String(80)),
        sa.Column("tokens_entrada", sa.Integer(), nullable=False),
        sa.Column("tokens_salida", sa.Integer(), nullable=False),
        sa.Column("latencia_ms", sa.Integer(), nullable=False),
        sa.Column("valoracion", sa.SmallInteger()),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id", "empresa_id"], ["usuario.id", "usuario.empresa_id"]),
    )
    op.create_index("ix_interaccion_ia_empresa_id", "interaccion_ia", ["empresa_id"])
    op.create_index(
        "ix_interaccion_ia_empresa_fecha", "interaccion_ia", ["empresa_id", "creado_en"]
    )
    op.create_index(
        "ix_interaccion_ia_conversacion", "interaccion_ia", ["empresa_id", "conversacion_id"]
    )


def downgrade():
    op.drop_index("ix_interaccion_ia_conversacion", table_name="interaccion_ia")
    op.drop_index("ix_interaccion_ia_empresa_fecha", table_name="interaccion_ia")
    op.drop_index("ix_interaccion_ia_empresa_id", table_name="interaccion_ia")
    op.drop_table("interaccion_ia")
