"""Agrega alertas de vencimiento por lote.

Revision ID: a619f7d84c2e
Revises: ee0ee13d6287
"""

from alembic import op
import sqlalchemy as sa

revision = "a619f7d84c2e"
down_revision = "ee0ee13d6287"
branch_labels = None
depends_on = None


TIPOS_ANTERIORES = (
    "tipo IN ("
    "'stock_bajo',"
    "'sobrestock',"
    "'riesgo_agotamiento',"
    "'sin_movimiento',"
    "'recomendacion_compra'"
    ")"
)

TIPOS_NUEVOS = (
    "tipo IN ("
    "'stock_bajo',"
    "'sobrestock',"
    "'riesgo_agotamiento',"
    "'sin_movimiento',"
    "'recomendacion_compra',"
    "'lote_proximo_vencer',"
    "'lote_vence_hoy',"
    "'lote_vencido'"
    ")"
)


def upgrade():
    with op.batch_alter_table(
        "alerta_inventario",
        schema=None,
    ) as batch_op:
        batch_op.drop_index(
            "uq_alerta_activa",
            postgresql_where=sa.text("estado = 'activa'"),
            sqlite_where=sa.text("estado = 'activa'"),
        )
        batch_op.drop_constraint(
            "ck_alerta_tipo",
            type_="check",
        )
        batch_op.add_column(
            sa.Column(
                "lote_id",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_alerta_lote_empresa",
            "lote",
            ["lote_id", "empresa_id"],
            ["id", "empresa_id"],
        )
        batch_op.create_check_constraint(
            "ck_alerta_tipo",
            TIPOS_NUEVOS,
        )
        batch_op.create_index(
            "ix_alerta_lote_id",
            ["lote_id"],
            unique=False,
        )
        batch_op.create_index(
            "uq_alerta_activa",
            [
                "empresa_id",
                "producto_id",
                "bodega_id",
                "tipo",
            ],
            unique=True,
            postgresql_where=sa.text("estado = 'activa' " "AND lote_id IS NULL"),
            sqlite_where=sa.text("estado = 'activa' " "AND lote_id IS NULL"),
        )
        batch_op.create_index(
            "uq_alerta_lote_activa",
            [
                "empresa_id",
                "lote_id",
                "tipo",
            ],
            unique=True,
            postgresql_where=sa.text("estado = 'activa' " "AND lote_id IS NOT NULL"),
            sqlite_where=sa.text("estado = 'activa' " "AND lote_id IS NOT NULL"),
        )


def downgrade():
    # La versión anterior no puede representar
    # alertas vinculadas a lotes.
    op.execute(sa.text("DELETE FROM alerta_inventario " "WHERE lote_id IS NOT NULL"))

    with op.batch_alter_table(
        "alerta_inventario",
        schema=None,
    ) as batch_op:
        batch_op.drop_index(
            "uq_alerta_lote_activa",
            postgresql_where=sa.text("estado = 'activa' " "AND lote_id IS NOT NULL"),
            sqlite_where=sa.text("estado = 'activa' " "AND lote_id IS NOT NULL"),
        )
        batch_op.drop_index(
            "uq_alerta_activa",
            postgresql_where=sa.text("estado = 'activa' " "AND lote_id IS NULL"),
            sqlite_where=sa.text("estado = 'activa' " "AND lote_id IS NULL"),
        )
        batch_op.drop_index("ix_alerta_lote_id")
        batch_op.drop_constraint(
            "ck_alerta_tipo",
            type_="check",
        )
        batch_op.drop_constraint(
            "fk_alerta_lote_empresa",
            type_="foreignkey",
        )
        batch_op.drop_column("lote_id")
        batch_op.create_check_constraint(
            "ck_alerta_tipo",
            TIPOS_ANTERIORES,
        )
        batch_op.create_index(
            "uq_alerta_activa",
            [
                "empresa_id",
                "producto_id",
                "bodega_id",
                "tipo",
            ],
            unique=True,
            postgresql_where=sa.text("estado = 'activa'"),
            sqlite_where=sa.text("estado = 'activa'"),
        )
