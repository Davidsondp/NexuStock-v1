"""Agrega presentaciones comerciales a ventas.

Revision ID: ab7ae6131661
Revises: 5e168f68eeb6
Create Date: 2026-08-16 16:42:14.751111
"""

from alembic import op
import sqlalchemy as sa

revision = "ab7ae6131661"
down_revision = "5e168f68eeb6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "venta_item",
        schema=None,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "presentacion_id",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "presentacion_codigo",
                sa.String(length=50),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "presentacion_nombre",
                sa.String(length=100),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "presentacion_abreviatura",
                sa.String(length=20),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "cantidad_presentacion",
                sa.Numeric(
                    precision=14,
                    scale=3,
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "factor_conversion",
                sa.Numeric(
                    precision=14,
                    scale=3,
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "precio_presentacion",
                sa.Numeric(
                    precision=14,
                    scale=2,
                ),
                nullable=True,
            )
        )

    op.execute(sa.text("""
            UPDATE venta_item
            SET
                cantidad_presentacion = cantidad,
                factor_conversion = 1,
                precio_presentacion = precio_unitario
            WHERE
                cantidad_presentacion IS NULL
                OR factor_conversion IS NULL
                OR precio_presentacion IS NULL
            """))

    with op.batch_alter_table(
        "venta_item",
        schema=None,
    ) as batch_op:
        batch_op.alter_column(
            "cantidad_presentacion",
            existing_type=sa.Numeric(
                precision=14,
                scale=3,
            ),
            nullable=False,
        )
        batch_op.alter_column(
            "factor_conversion",
            existing_type=sa.Numeric(
                precision=14,
                scale=3,
            ),
            nullable=False,
        )
        batch_op.alter_column(
            "precio_presentacion",
            existing_type=sa.Numeric(
                precision=14,
                scale=2,
            ),
            nullable=False,
        )
        batch_op.create_foreign_key(
            ("fk_venta_item_presentacion_" "empresa"),
            "presentacion_producto",
            [
                "presentacion_id",
                "empresa_id",
            ],
            [
                "id",
                "empresa_id",
            ],
        )
        batch_op.create_check_constraint(
            ("ck_venta_item_presentacion_" "cantidades"),
            ("cantidad_presentacion > 0 " "AND factor_conversion > 0"),
        )
        batch_op.create_check_constraint(
            ("ck_venta_item_presentacion_" "precio"),
            "precio_presentacion >= 0",
        )


def downgrade():
    with op.batch_alter_table(
        "venta_item",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            ("ck_venta_item_presentacion_" "precio"),
            type_="check",
        )
        batch_op.drop_constraint(
            ("ck_venta_item_presentacion_" "cantidades"),
            type_="check",
        )
        batch_op.drop_constraint(
            ("fk_venta_item_presentacion_" "empresa"),
            type_="foreignkey",
        )
        batch_op.drop_column("precio_presentacion")
        batch_op.drop_column("factor_conversion")
        batch_op.drop_column("cantidad_presentacion")
        batch_op.drop_column("presentacion_abreviatura")
        batch_op.drop_column("presentacion_nombre")
        batch_op.drop_column("presentacion_codigo")
        batch_op.drop_column("presentacion_id")
