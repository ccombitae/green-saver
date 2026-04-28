from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

from app.core.config import settings


def get_connection():
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL no configurada")

    return psycopg2.connect(settings.database_url)


@contextmanager
def db_cursor():
    connection = get_connection()
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
    finally:
        connection.close()
