from alembic import op

revision = "0002_procedimientos_y_triggers"
down_revision = "0001_esquema_normalizado"
branch_labels = None
depends_on = None

FUNCIONES = r"""
CREATE OR REPLACE FUNCTION fn_actualizar_marca_tiempo() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.actualizado_en := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_usuarios_actualizado_en
BEFORE UPDATE ON usuarios
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_marca_tiempo();

CREATE TRIGGER trg_sistemas_actualizado_en
BEFORE UPDATE ON sistemas_instalados
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_marca_tiempo();

CREATE OR REPLACE FUNCTION fn_validar_cotizacion() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_estado_nuevo VARCHAR(20);
    v_estado_anterior VARCHAR(20);
BEGIN
    SELECT codigo INTO v_estado_nuevo FROM estados_cotizacion WHERE id = NEW.estado_id;

    IF TG_OP = 'UPDATE' THEN
        SELECT codigo INTO v_estado_anterior FROM estados_cotizacion WHERE id = OLD.estado_id;
        IF v_estado_anterior = 'accepted' AND v_estado_nuevo <> 'accepted' THEN
            RAISE EXCEPTION 'La cotización % ya fue aceptada y no puede cambiar de estado', OLD.id
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF v_estado_nuevo = 'accepted' THEN
        IF NEW.fecha_instalacion IS NULL THEN
            RAISE EXCEPTION 'Una cotización aceptada debe tener fecha de instalación'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.fecha_instalacion < NEW.enviada_en::date THEN
            RAISE EXCEPTION 'La fecha de instalación (%) no puede ser anterior al envío de la cotización (%)',
                NEW.fecha_instalacion, NEW.enviada_en::date
                USING ERRCODE = 'check_violation';
        END IF;
        NEW.aceptada_en := COALESCE(NEW.aceptada_en, now());
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_cotizaciones_validar
BEFORE INSERT OR UPDATE ON cotizaciones
FOR EACH ROW EXECUTE FUNCTION fn_validar_cotizacion();

CREATE OR REPLACE FUNCTION fn_auditar_estado_cotizacion() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.estado_id IS DISTINCT FROM OLD.estado_id THEN
        INSERT INTO auditoria_cotizaciones (cotizacion_id, estado_anterior, estado_nuevo)
        VALUES (
            NEW.id,
            CASE WHEN TG_OP = 'UPDATE' THEN (SELECT codigo FROM estados_cotizacion WHERE id = OLD.estado_id) END,
            (SELECT codigo FROM estados_cotizacion WHERE id = NEW.estado_id)
        );
    END IF;
    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_cotizaciones_auditar
AFTER INSERT OR UPDATE OF estado_id ON cotizaciones
FOR EACH ROW EXECUTE FUNCTION fn_auditar_estado_cotizacion();

CREATE OR REPLACE PROCEDURE aceptar_cotizacion(
    IN p_cotizacion_id INTEGER,
    IN p_fecha_instalacion DATE,
    INOUT p_sistema_id INTEGER DEFAULT NULL
)
LANGUAGE plpgsql AS $$
DECLARE
    v_cotizacion cotizaciones%ROWTYPE;
    v_estado VARCHAR(20);
    v_estado_aceptada SMALLINT;
    v_potencia NUMERIC(8, 2);
BEGIN
    IF p_fecha_instalacion IS NULL THEN
        RAISE EXCEPTION 'La fecha de instalación es obligatoria' USING ERRCODE = 'invalid_parameter_value';
    END IF;

    SELECT * INTO v_cotizacion FROM cotizaciones WHERE id = p_cotizacion_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La cotización % no existe', p_cotizacion_id USING ERRCODE = 'no_data_found';
    END IF;

    SELECT codigo INTO v_estado FROM estados_cotizacion WHERE id = v_cotizacion.estado_id;
    IF v_estado = 'accepted' THEN
        RAISE EXCEPTION 'La cotización % ya fue aceptada', p_cotizacion_id USING ERRCODE = 'invalid_parameter_value';
    END IF;

    SELECT id INTO v_estado_aceptada FROM estados_cotizacion WHERE codigo = 'accepted';

    SELECT round(sum(d.cantidad * e.potencia_w) / 1000, 2)
      INTO v_potencia
      FROM detalle_cotizacion d
      JOIN equipos e ON e.id = d.equipo_id
      JOIN tipos_equipo t ON t.id = e.tipo_equipo_id
     WHERE d.cotizacion_id = p_cotizacion_id AND t.codigo = 'panel';

    IF v_potencia IS NULL OR v_potencia = 0 THEN
        SELECT NULLIF(round(c.paneles * 0.55, 2), 0) INTO v_potencia FROM calculos c WHERE c.id = v_cotizacion.calculo_id;
    END IF;

    BEGIN
        UPDATE cotizaciones
           SET estado_id = v_estado_aceptada,
               aceptada_en = now(),
               fecha_instalacion = p_fecha_instalacion,
               version = version + 1
         WHERE id = p_cotizacion_id;

        INSERT INTO sistemas_instalados (usuario_id, cotizacion_id, potencia_kwp, fecha_instalacion)
        VALUES (v_cotizacion.cliente_id, p_cotizacion_id, v_potencia, p_fecha_instalacion)
        ON CONFLICT (usuario_id) DO UPDATE
           SET cotizacion_id = EXCLUDED.cotizacion_id,
               potencia_kwp = EXCLUDED.potencia_kwp,
               fecha_instalacion = EXCLUDED.fecha_instalacion
        RETURNING id INTO p_sistema_id;

        DELETE FROM equipos_sistema WHERE sistema_id = p_sistema_id;

        INSERT INTO equipos_sistema (sistema_id, equipo_id, cantidad)
        SELECT p_sistema_id, d.equipo_id, d.cantidad
          FROM detalle_cotizacion d
         WHERE d.cotizacion_id = p_cotizacion_id;
    EXCEPTION
        WHEN check_violation OR foreign_key_violation OR unique_violation OR not_null_violation THEN
            RAISE EXCEPTION 'No se pudo aceptar la cotización %: %', p_cotizacion_id, SQLERRM
                USING ERRCODE = SQLSTATE;
    END;
END;
$$;

CREATE OR REPLACE FUNCTION fn_estadisticas_mensuales(p_desde DATE, p_hasta DATE)
RETURNS TABLE (mes DATE, calculos BIGINT, paneles_promedio NUMERIC, ahorro_total_cop NUMERIC)
LANGUAGE sql STABLE AS $$
    SELECT date_trunc('month', c.creado_en)::date AS mes,
           count(*) AS calculos,
           round(avg(c.paneles), 2) AS paneles_promedio,
           sum(c.ahorro_estimado_cop) AS ahorro_total_cop
      FROM calculos c
     WHERE c.creado_en >= p_desde
       AND c.creado_en < p_hasta + 1
     GROUP BY 1
     ORDER BY 1;
$$;
"""

ELIMINAR = """
DROP FUNCTION IF EXISTS fn_estadisticas_mensuales(DATE, DATE);
DROP PROCEDURE IF EXISTS aceptar_cotizacion(INTEGER, DATE, INTEGER);
DROP TRIGGER IF EXISTS trg_cotizaciones_auditar ON cotizaciones;
DROP FUNCTION IF EXISTS fn_auditar_estado_cotizacion();
DROP TRIGGER IF EXISTS trg_cotizaciones_validar ON cotizaciones;
DROP FUNCTION IF EXISTS fn_validar_cotizacion();
DROP TRIGGER IF EXISTS trg_sistemas_actualizado_en ON sistemas_instalados;
DROP TRIGGER IF EXISTS trg_usuarios_actualizado_en ON usuarios;
DROP FUNCTION IF EXISTS fn_actualizar_marca_tiempo();
"""


def upgrade() -> None:
    op.execute(FUNCIONES)


def downgrade() -> None:
    op.execute(ELIMINAR)
