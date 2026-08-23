"""Agrega presentaciones y unidades de medida.

Revision ID: 3f6b8c9e2193
Revises: a619f7d84c2e
Create Date: 2026-08-15 21:00:00.535205
"""

from alembic import op
import sqlalchemy as sa

revision = "3f6b8c9e2193"
down_revision = "a619f7d84c2e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "presentacion_producto",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "producto_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "codigo",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "nombre",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "abreviatura",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "factor_base",
            sa.Numeric(
                precision=14,
                scale=3,
            ),
            nullable=False,
        ),
        sa.Column(
            "activa",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "creado_en",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "factor_base > 0",
            name=("ck_presentacion_producto_" "factor_positivo"),
        ),
        sa.ForeignKeyConstraint(
            [
                "producto_id",
                "empresa_id",
            ],
            [
                "producto.id",
                "producto.empresa_id",
            ],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "empresa_id",
            "producto_id",
            "codigo",
            name=("uq_presentacion_producto_" "empresa_codigo"),
        ),
        sa.UniqueConstraint(
            "id",
            "empresa_id",
            name=("uq_presentacion_producto_" "id_empresa"),
        ),
    )

    op.create_index(
        "ix_presentacion_producto_empresa",
        "presentacion_producto",
        [
            "empresa_id",
            "producto_id",
            "activa",
        ],
        unique=False,
    )

    presentacion = sa.table(
        "presentacion_producto",
        sa.column(
            "empresa_id",
            sa.Integer(),
        ),
        sa.column(
            "producto_id",
            sa.Integer(),
        ),
        sa.column(
            "codigo",
            sa.String(length=50),
        ),
        sa.column(
            "nombre",
            sa.String(length=100),
        ),
        sa.column(
            "abreviatura",
            sa.String(length=20),
        ),
        sa.column(
            "factor_base",
            sa.Numeric(
                precision=14,
                scale=3,
            ),
        ),
        sa.column(
            "activa",
            sa.Boolean(),
        ),
        sa.column(
            "creado_en",
            sa.DateTime(),
        ),
        sa.column(
            "actualizado_en",
            sa.DateTime(),
        ),
    )

    producto = sa.table(
        "producto",
        sa.column(
            "id",
            sa.Integer(),
        ),
        sa.column(
            "empresa_id",
            sa.Integer(),
        ),
        sa.column(
            "unidades_por_caja",
            sa.Numeric(
                precision=12,
                scale=3,
            ),
        ),
        sa.column(
            "activo",
            sa.Boolean(),
        ),
    )

    ahora = sa.func.current_timestamp()

    consulta_cajas = sa.select(
        producto.c.empresa_id,
        producto.c.id,
        sa.literal("CAJA"),
        sa.literal("Caja"),
        sa.literal("cj"),
        producto.c.unidades_por_caja,
        producto.c.activo,
        ahora,
        ahora,
    ).where(producto.c.unidades_por_caja > 1)

    op.get_bind().execute(
        sa.insert(presentacion).from_select(
            [
                "empresa_id",
                "producto_id",
                "codigo",
                "nombre",
                "abreviatura",
                "factor_base",
                "activa",
                "creado_en",
                "actualizado_en",
            ],
            consulta_cajas,
        )
    )


def downgrade():
    op.drop_index(
        "ix_presentacion_producto_empresa",
        table_name="presentacion_producto",
    )
    op.drop_table("presentacion_producto")
