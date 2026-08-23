"""Plan inicial gratuito, Enterprise y documentos automáticos.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""

from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "documento_facturacion_saas",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresa.id"), nullable=False),
        sa.Column("pago_id", sa.BigInteger(), sa.ForeignKey("pago.id"), nullable=False),
        sa.Column("numero", sa.String(length=40), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="emitido"),
        sa.Column("moneda", sa.String(length=3), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("cliente_nombre", sa.String(length=150), nullable=False),
        sa.Column("cliente_identificacion_fiscal", sa.String(length=30)),
        sa.Column("cliente_email", sa.String(length=254), nullable=False),
        sa.Column("concepto", sa.String(length=255), nullable=False),
        sa.Column("emitido_en", sa.DateTime(), nullable=False),
        sa.Column("datos", sa.JSON(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.CheckConstraint("tipo IN ('factura','recibo')", name="ck_documento_facturacion_tipo"),
        sa.CheckConstraint("estado IN ('emitido','anulado')", name="ck_documento_facturacion_estado"),
        sa.CheckConstraint("total >= 0", name="ck_documento_facturacion_total"),
        sa.UniqueConstraint("pago_id", name="uq_documento_facturacion_pago"),
        sa.UniqueConstraint("numero", name="uq_documento_facturacion_numero"),
    )
    op.create_index(
        "ix_documento_facturacion_empresa_fecha",
        "documento_facturacion_saas",
        ["empresa_id", "emitido_en"],
    )
    op.create_index(
        "ix_documento_facturacion_saas_empresa_id",
        "documento_facturacion_saas",
        ["empresa_id"],
    )
    op.execute(
        "UPDATE plan_saas SET nombre='Inicial', descripcion='Plan gratuito para comenzar', "
        "precio_mensual=0, precio_anual=0, limite_productos=100, limite_usuarios=1, "
        "limite_movimientos_mes=1000, nivel_comercial='inicio' WHERE codigo='basico'"
    )
    op.execute(
        "UPDATE plan_saas SET nombre='Enterprise', "
        "descripcion='Control empresarial para organizaciones de gran escala', "
        "limite_productos=10000, limite_usuarios=12, nivel_comercial='empresa' "
        "WHERE codigo='empresa'"
    )


def downgrade():
    op.execute(
        "UPDATE plan_saas SET nombre='Básico', descripcion='Para pequeños negocios', "
        "precio_mensual=9990, precio_anual=99900, limite_productos=500, "
        "limite_usuarios=2, limite_movimientos_mes=5000 WHERE codigo='basico'"
    )
    op.execute(
        "UPDATE plan_saas SET nombre='Empresa', descripcion='Control e inteligencia completa', "
        "limite_productos=NULL, limite_usuarios=NULL WHERE codigo='empresa'"
    )
    op.drop_index("ix_documento_facturacion_saas_empresa_id", table_name="documento_facturacion_saas")
    op.drop_index("ix_documento_facturacion_empresa_fecha", table_name="documento_facturacion_saas")
    op.drop_table("documento_facturacion_saas")
