"""Alinea solicitudes y pagos con el flujo financiero seguro.

Revision ID: f9a2c4d6e8b0
Revises: b8e1c3d5f7a9
"""

from alembic import op
import sqlalchemy as sa


revision = "f9a2c4d6e8b0"
down_revision = "b8e1c3d5f7a9"
branch_labels = None
depends_on = None


ESTADOS_PAGO_NUEVOS = (
    "'iniciado','procesando','pagado','rechazado','cancelado','vencido',"
    "'reembolsado','incidencia'"
)
ESTADOS_SOLICITUD_NUEVOS = (
    "'pendiente','pago_en_proceso','cancelacion_en_revision','aprobada',"
    "'cancelada','vencida'"
)


def upgrade():
    bind = op.get_bind()
    dialecto = bind.dialect.name

    # Los estados heredados se normalizan antes de endurecer las restricciones.
    op.execute("UPDATE pago SET estado = 'iniciado' WHERE estado = 'pendiente'")
    op.execute("UPDATE pago SET estado = 'cancelado' WHERE estado = 'anulado'")

    with op.batch_alter_table("pago") as batch:
        batch.drop_constraint("ck_pago_estado", type_="check")
        batch.create_check_constraint(
            "ck_pago_estado", f"estado IN ({ESTADOS_PAGO_NUEVOS})"
        )
        batch.add_column(sa.Column("fecha_vencimiento", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("plan_solicitado_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("ciclo", sa.String(10), nullable=True))

    op.execute(
        "UPDATE pago SET plan_solicitado_id = ("
        "SELECT plan_solicitado_id FROM solicitud_cambio_plan "
        "WHERE solicitud_cambio_plan.id = pago.solicitud_id), "
        "ciclo = (SELECT ciclo FROM solicitud_cambio_plan "
        "WHERE solicitud_cambio_plan.id = pago.solicitud_id)"
    )
    with op.batch_alter_table("pago") as batch:
        batch.alter_column("plan_solicitado_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("ciclo", existing_type=sa.String(10), nullable=False)
        batch.create_foreign_key(
            "fk_pago_plan_solicitado", "plan_saas", ["plan_solicitado_id"], ["id"]
        )
        batch.create_check_constraint(
            "ck_pago_ciclo", "ciclo IN ('mensual','anual')"
        )

    with op.batch_alter_table("solicitud_cambio_plan") as batch:
        batch.drop_constraint("ck_solicitud_estado", type_="check")
        batch.create_check_constraint(
            "ck_solicitud_estado", f"estado IN ({ESTADOS_SOLICITUD_NUEVOS})"
        )
        batch.add_column(sa.Column("proveedor_preferido", sa.String(50), nullable=True))

    op.drop_index("uq_solicitud_plan_pendiente", table_name="solicitud_cambio_plan")
    condicion = "estado IN ('pendiente','pago_en_proceso','cancelacion_en_revision')"
    op.create_index(
        "uq_solicitud_plan_pendiente",
        "solicitud_cambio_plan",
        ["empresa_id"],
        unique=True,
        postgresql_where=sa.text(condicion),
        sqlite_where=sa.text(condicion),
    )


def downgrade():
    # Estados sin equivalente histórico se conservan con el significado más seguro.
    op.execute("UPDATE pago SET estado = 'pendiente' WHERE estado = 'iniciado'")
    op.execute("UPDATE pago SET estado = 'anulado' WHERE estado IN ('cancelado','vencido')")
    op.execute("UPDATE pago SET estado = 'rechazado' WHERE estado = 'incidencia'")
    op.execute(
        "UPDATE solicitud_cambio_plan SET estado = 'pendiente' "
        "WHERE estado IN ('pago_en_proceso','cancelacion_en_revision')"
    )
    op.execute("UPDATE solicitud_cambio_plan SET estado = 'cancelada' WHERE estado = 'vencida'")

    op.drop_index("uq_solicitud_plan_pendiente", table_name="solicitud_cambio_plan")
    op.create_index(
        "uq_solicitud_plan_pendiente",
        "solicitud_cambio_plan",
        ["empresa_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'pendiente'"),
        sqlite_where=sa.text("estado = 'pendiente'"),
    )
    with op.batch_alter_table("solicitud_cambio_plan") as batch:
        batch.drop_column("proveedor_preferido")
        batch.drop_constraint("ck_solicitud_estado", type_="check")
        batch.create_check_constraint(
            "ck_solicitud_estado",
            "estado IN ('pendiente','aprobada','rechazada','cancelada')",
        )
    with op.batch_alter_table("pago") as batch:
        batch.drop_constraint("ck_pago_ciclo", type_="check")
        batch.drop_constraint("fk_pago_plan_solicitado", type_="foreignkey")
        batch.drop_column("ciclo")
        batch.drop_column("plan_solicitado_id")
        batch.drop_column("fecha_vencimiento")
        batch.drop_constraint("ck_pago_estado", type_="check")
        batch.create_check_constraint(
            "ck_pago_estado",
            "estado IN ('pendiente','procesando','pagado','rechazado','anulado','reembolsado')",
        )
