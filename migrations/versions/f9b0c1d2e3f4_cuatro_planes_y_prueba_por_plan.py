"""Cuatro planes comerciales y prueba asociada al plan elegido.

Revision ID: f9b0c1d2e3f4
Revises: f8a9b0c1d2e3
"""

from alembic import op

revision = "f9b0c1d2e3f4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE plan_saas SET dias_prueba=30 "
        "WHERE codigo IN ('avanzado','ultra','profesional','empresa')"
    )
    op.execute(
        "UPDATE plan_saas SET activo=FALSE, nombre='Prueba heredada', "
        "descripcion='Compatibilidad histórica; la prueba pertenece al plan elegido' "
        "WHERE codigo='prueba'"
    )
    op.execute("UPDATE plan_saas SET activo=FALSE WHERE codigo IN ('basico','corporativo')")


def downgrade():
    op.execute(
        "UPDATE plan_saas SET dias_prueba=0 "
        "WHERE codigo IN ('avanzado','ultra','profesional','empresa')"
    )
    op.execute(
        "UPDATE plan_saas SET activo=TRUE, nombre='Prueba gratuita', "
        "descripcion='Prueba gratuita con funciones profesionales' "
        "WHERE codigo='prueba'"
    )
    op.execute("UPDATE plan_saas SET activo=TRUE WHERE codigo IN ('basico','corporativo')")
