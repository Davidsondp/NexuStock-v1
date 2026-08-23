"""Alinea capacidades con los límites de Ultra y Profesional.

Revision ID: f7a8b9c0d1e2
Revises: f6a7b8c9d0e1
"""

from alembic import op
import sqlalchemy as sa


revision = "f7a8b9c0d1e2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


plan_saas = sa.table(
    "plan_saas",
    sa.column("codigo", sa.String()),
    sa.column("funciones", sa.JSON()),
)


def _actualizar(valor: bool) -> None:
    conexion = op.get_bind()
    filas = conexion.execute(
        sa.select(plan_saas.c.codigo, plan_saas.c.funciones).where(
            plan_saas.c.codigo.in_(("ultra", "profesional"))
        )
    )
    for codigo, funciones in filas:
        nuevas = dict(funciones or {})
        nuevas.update(
            {
                "multisucursal": valor,
                "multibodega": valor,
                "transferencias": valor,
            }
        )
        conexion.execute(
            plan_saas.update().where(plan_saas.c.codigo == codigo).values(funciones=nuevas)
        )


def upgrade():
    _actualizar(True)


def downgrade():
    _actualizar(False)
