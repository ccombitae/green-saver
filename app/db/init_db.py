"""Crea las tablas al arrancar la API si INIT_DB=true.

El script schema.sql es idempotente (CREATE ... IF NOT EXISTS, ON CONFLICT DO
NOTHING), así que ejecutarlo en cada arranque no borra ni duplica datos. El
bloqueo consultivo evita que dos workers de gunicorn lo ejecuten a la vez.
"""
import logging
import os
from pathlib import Path

from app.db.database import get_connection

log = logging.getLogger("green_saver.init_db")
SCHEMA = Path(__file__).with_name("schema.sql")
LOCK_ID = 7_310_455  # número arbitrario y fijo para pg_advisory_lock


def init_db_if_enabled() -> None:
    if os.getenv("INIT_DB", "false").lower() != "true":
        return
    try:
        connection = get_connection()
    except Exception as exc:  # la API debe arrancar aunque la BD no responda
        log.error("No se pudo conectar para crear las tablas: %s", exc)
        return
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
                try:
                    cursor.execute(SCHEMA.read_text(encoding="utf-8"))
                finally:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
        log.info("Esquema de base de datos verificado")
    except Exception as exc:
        log.error("Error al crear las tablas: %s", exc)
    finally:
        connection.close()
