"""Agrega trazabilidad farmaceutica por lote.

Revision ID: ee0ee13d6287
Revises: 5fde68443c14
"""

from alembic import op
import sqlalchemy as sa

revision = "ee0ee13d6287"
down_revision = "5fde68443c14"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "lote",
        schema=None,
    ) as batch_op:
        batch_op.create_unique_constraint(
            "uq_lote_id_empresa",
            ["id", "empresa_id"],
        )

    with op.batch_alter_table(
        "movimiento",
        schema=None,
    ) as batch_op:
        batch_op.create_unique_constraint(
            "uq_movimiento_id_empresa",
            ["id", "empresa_id"],
        )

    op.create_table(
        "movimiento_lote",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(
                sa.Integer(),
                "sqlite",
            ),
            nullable=False,
        ),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "movimiento_id",
            sa.BigInteger().with_variant(
                sa.Integer(),
                "sqlite",
            ),
            nullable=False,
        ),
        sa.Column(
            "lote_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "producto_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "bodega_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "cantidad",
            sa.Numeric(14, 3),
            nullable=False,
        ),
        sa.Column(
            "saldo_anterior",
            sa.Numeric(14, 3),
            nullable=False,
        ),
        sa.Column(
            "saldo_nuevo",
            sa.Numeric(14, 3),
            nullable=False,
        ),
        sa.Column(
            "fecha",
            sa.DateTime(),
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
            "cantidad <> 0",
            name="ck_movimiento_lote_cantidad",
        ),
        sa.CheckConstraint(
            ("saldo_anterior >= 0 " "AND saldo_nuevo >= 0"),
            name="ck_movimiento_lote_saldos",
        ),
        sa.CheckConstraint(
            ("saldo_nuevo = " "saldo_anterior + cantidad"),
            name="ck_movimiento_lote_ecuacion",
        ),
        sa.ForeignKeyConstraint(
            ["bodega_id", "empresa_id"],
            ["bodega.id", "bodega.empresa_id"],
        ),
        sa.ForeignKeyConstraint(
            ["lote_id", "empresa_id"],
            ["lote.id", "lote.empresa_id"],
        ),
        sa.ForeignKeyConstraint(
            ["movimiento_id", "empresa_id"],
            [
                "movimiento.id",
                "movimiento.empresa_id",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["producto_id", "empresa_id"],
            [
                "producto.id",
                "producto.empresa_id",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "movimiento_id",
            "lote_id",
            name="uq_movimiento_lote_traza",
        ),
    )

    with op.batch_alter_table(
        "movimiento_lote",
        schema=None,
    ) as batch_op:
        batch_op.create_index(
            "ix_movimiento_lote_bodega_id",
            ["bodega_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_movimiento_lote_empresa_fecha",
            ["empresa_id", "fecha"],
            unique=False,
        )
        batch_op.create_index(
            "ix_movimiento_lote_empresa_id",
            ["empresa_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_movimiento_lote_lote_fecha",
            ["lote_id", "fecha"],
            unique=False,
        )
        batch_op.create_index(
            "ix_movimiento_lote_lote_id",
            ["lote_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_movimiento_lote_movimiento_id",
            ["movimiento_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_movimiento_lote_producto_id",
            ["producto_id"],
            unique=False,
        )


def downgrade():
    op.drop_table("movimiento_lote")

    with op.batch_alter_table(
        "movimiento",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            "uq_movimiento_id_empresa",
            type_="unique",
        )

    with op.batch_alter_table(
        "lote",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            "uq_lote_id_empresa",
            type_="unique",
        )
