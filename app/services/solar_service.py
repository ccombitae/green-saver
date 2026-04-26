from datetime import datetime

from app.db.database import db_cursor
from app.schemas.solar import CalculoCrear


def list_calculos() -> list[dict]:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, email, consumption, estimatedPanels, coverage,
                   estimatedSavings, recommendation, created_at
            FROM calculos_sistema
            ORDER BY created_at DESC
            """
        )
        return cursor.fetchall()


def create_calculo(payload: CalculoCrear) -> dict:
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO calculos_sistema (
                email, consumption, estimatedPanels, coverage,
                estimatedSavings, recommendation, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id, created_at
            """,
            (
                payload.email,
                payload.consumption,
                payload.estimatedPanels,
                payload.coverage,
                payload.estimatedSavings,
                payload.recommendation,
            ),
        )
        created_row = cursor.fetchone()

    return {
        "id": created_row["id"],
        "email": payload.email,
        "consumption": payload.consumption,
        "estimatedPanels": payload.estimatedPanels,
        "coverage": payload.coverage,
        "estimatedSavings": payload.estimatedSavings,
        "recommendation": payload.recommendation,
        "created_at": created_row["created_at"].isoformat(),
    }


def update_calculo(
    calculo_id: int,
    usuario_id: int,
    panel_id: int,
    inversor_id: int,
    bateria_id: int,
    paneles_necesarios: int,
    inversor_kw: float,
    bateria_kwh: float,
    costo_total: float,
) -> dict:
    with db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE calculos_sistema
            SET usuario_id = %s,
                panel_id = %s,
                inversor_id = %s,
                bateria_id = %s,
                paneles_necesarios = %s,
                inversor_kw = %s,
                bateria_kwh = %s,
                costo_total = %s
            WHERE id = %s
            """,
            (
                usuario_id,
                panel_id,
                inversor_id,
                bateria_id,
                paneles_necesarios,
                inversor_kw,
                bateria_kwh,
                costo_total,
                calculo_id,
            ),
        )

    return {"message": "Cálculo actualizado"}


def delete_calculo(calculo_id: int) -> dict:
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM calculos_sistema WHERE id = %s", (calculo_id,))

    return {"message": "Cálculo eliminado"}


def report_general() -> list[dict]:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                c.id,
                COALESCE(u.nombre, c.email) AS nombre,
                c.email,
                c.consumption,
                c.estimatedPanels,
                c.coverage,
                c.estimatedSavings,
                c.recommendation,
                c.created_at
            FROM calculos_sistema c
            LEFT JOIN usuarios u ON LOWER(u.email) = LOWER(c.email)
            ORDER BY c.created_at DESC
            """
        )
        return cursor.fetchall()
