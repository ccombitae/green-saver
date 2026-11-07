from alembic import op

revision = "0003_indices_optimizacion"
down_revision = "0002_procedimientos_y_triggers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_calculos_usuario_fecha ON calculos (usuario_id, creado_en DESC) "
        "INCLUDE (consumo_mensual_kwh, paneles, cobertura_pct, ahorro_estimado_cop)"
    )
    op.execute("CREATE INDEX ix_calculos_creado_en ON calculos (creado_en)")
    op.execute("CREATE INDEX ix_calculos_ciudad_id ON calculos (ciudad_id)")
    op.execute("CREATE INDEX ix_cotizaciones_estado_enviada ON cotizaciones (estado_id, enviada_en DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cotizaciones_estado_enviada")
    op.execute("DROP INDEX IF EXISTS ix_calculos_ciudad_id")
    op.execute("DROP INDEX IF EXISTS ix_calculos_creado_en")
    op.execute("DROP INDEX IF EXISTS ix_calculos_usuario_fecha")
