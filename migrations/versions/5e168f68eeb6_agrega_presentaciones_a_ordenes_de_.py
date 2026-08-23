"""Agrega presentaciones a órdenes de compra.

Revision ID: 5e168f68eeb6
Revises: 3f6b8c9e2193
Create Date: 2026-08-16 14:31:32.139241
"""

from alembic import op
import sqlalchemy as sa

revision = "5e168f68eeb6"
down_revision = "3f6b8c9e2193"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "orden_compra_item",
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
                    scale=4,
                ),
                nullable=True,
            )
        )

    with op.batch_alter_table(
        "recepcion_compra_item",
        schema=None,
    ) as batch_op:
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
                "costo_presentacion",
                sa.Numeric(
                    precision=14,
                    scale=4,
                ),
                nullable=True,
            )
        )

    items = sa.table(
        "orden_compra_item",
        sa.column(
            "cantidad",
            sa.Numeric(
                precision=14,
                scale=3,
            ),
        ),
        sa.column(
            "precio_unitario",
            sa.Numeric(
                precision=14,
                scale=4,
            ),
        ),
        sa.column(
            "cantidad_presentacion",
            sa.Numeric(
                precision=14,
                scale=3,
            ),
        ),
        sa.column(
            "factor_conversion",
            sa.Numeric(
                precision=14,
                scale=3,
            ),
        ),
        sa.column(
            "precio_presentacion",
            sa.Numeric(
                precision=14,
                scale=4,
            ),
        ),
    )

    op.get_bind().execute(
        sa.update(items).values(
            cantidad_presentacion=items.c.cantidad,
            factor_conversion=sa.literal(1),
            precio_presentacion=items.c.precio_unitario,
        )
    )

    recepciones = sa.table(
        "recepcion_compra_item",
        sa.column(
            "cantidad",
            sa.Numeric(
                precision=14,
                scale=3,
            ),
        ),
        sa.column(
            "costo_unitario",
            sa.Numeric(
                precision=14,
                scale=4,
            ),
        ),
        sa.column(
            "cantidad_presentacion",
            sa.Numeric(
                precision=14,
                scale=3,
            ),
        ),
        sa.column(
            "factor_conversion",
            sa.Numeric(
                precision=14,
                scale=3,
            ),
        ),
        sa.column(
            "costo_presentacion",
            sa.Numeric(
                precision=14,
                scale=4,
            ),
        ),
    )

    op.get_bind().execute(
        sa.update(recepciones).values(
            cantidad_presentacion=recepciones.c.cantidad,
            factor_conversion=sa.literal(1),
            costo_presentacion=recepciones.c.costo_unitario,
        )
    )

    with op.batch_alter_table(
        "orden_compra_item",
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
                scale=4,
            ),
            nullable=False,
        )
        batch_op.create_foreign_key(
            ("fk_orden_item_" "presentacion_empresa"),
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
            ("ck_orden_item_presentacion_" "cantidades"),
            ("cantidad_presentacion > 0 " "AND factor_conversion > 0"),
        )
        batch_op.create_check_constraint(
            ("ck_orden_item_presentacion_" "precio"),
            "precio_presentacion >= 0",
        )
    with op.batch_alter_table(
        "recepcion_compra_item",
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
            "costo_presentacion",
            existing_type=sa.Numeric(
                precision=14,
                scale=4,
            ),
            nullable=False,
        )
        batch_op.create_check_constraint(
            ("ck_recepcion_item_" "presentacion_cantidades"),
            ("cantidad_presentacion > 0 " "AND factor_conversion > 0"),
        )
        batch_op.create_check_constraint(
            ("ck_recepcion_item_" "presentacion_costo"),
            "costo_presentacion >= 0",
        )


def downgrade():
    with op.batch_alter_table(
        "recepcion_compra_item",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            ("ck_recepcion_item_" "presentacion_costo"),
            type_="check",
        )
        batch_op.drop_constraint(
            ("ck_recepcion_item_" "presentacion_cantidades"),
            type_="check",
        )
        batch_op.drop_column("costo_presentacion")
        batch_op.drop_column("factor_conversion")
        batch_op.drop_column("cantidad_presentacion")

    with op.batch_alter_table(
        "orden_compra_item",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            ("ck_orden_item_presentacion_" "precio"),
            type_="check",
        )
        batch_op.drop_constraint(
            ("ck_orden_item_presentacion_" "cantidades"),
            type_="check",
        )
        batch_op.drop_constraint(
            ("fk_orden_item_" "presentacion_empresa"),
            type_="foreignkey",
        )
        batch_op.drop_column("precio_presentacion")
        batch_op.drop_column("factor_conversion")
        batch_op.drop_column("cantidad_presentacion")
        batch_op.drop_column("presentacion_abreviatura")
        batch_op.drop_column("presentacion_nombre")
        batch_op.drop_column("presentacion_codigo")
        batch_op.drop_column("presentacion_id")
