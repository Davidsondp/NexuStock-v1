"""Separa la jefatura empresarial del Super Admin global.

Revision ID: a7d9e2f4b6c8
Revises: f4c8a1b2d3e4
"""

import sqlalchemy as sa
from alembic import op

revision = "a7d9e2f4b6c8"
down_revision = "f4c8a1b2d3e4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.drop_constraint("ck_usuario_rol", type_="check")

    op.execute(sa.text("UPDATE usuario SET rol = 'jefe' " "WHERE rol = 'admin_empresa'"))

    with op.batch_alter_table("usuario") as batch_op:
        batch_op.create_check_constraint(
            "ck_usuario_rol",
            "rol IN ('super_admin','jefe','supervisor','empleado')",
        )


def downgrade():
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.drop_constraint("ck_usuario_rol", type_="check")

    op.execute(sa.text("UPDATE usuario SET rol = 'admin_empresa' " "WHERE rol = 'jefe'"))

    with op.batch_alter_table("usuario") as batch_op:
        batch_op.create_check_constraint(
            "ck_usuario_rol",
            "rol IN ('super_admin','admin_empresa','supervisor','empleado')",
        )
