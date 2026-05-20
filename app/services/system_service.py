import json

from app.db.database import db_cursor
from app.schemas.systems import SystemAssignRequest


def _ensure_systems_table() -> None:
    with db_cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sistemas_instalados (
                id SERIAL PRIMARY KEY,
                usuario_id INT NOT NULL UNIQUE,
                system JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
            """
        )


def _normalize_system(row: dict) -> dict:
    raw_system = row.get("system") or {}
    if isinstance(raw_system, str):
        try:
            system = json.loads(raw_system)
        except Exception:
            system = {}
    else:
        system = raw_system

    return {
        "id": row.get("id"),
        "userId": row.get("usuario_id"),
        "email": row.get("email"),
        "name": row.get("nombre"),
        "capacity": system.get("capacity", ""),
        "panels": system.get("panels", ""),
        "inverter": system.get("inverter", ""),
        "battery": system.get("battery", ""),
        "installDate": system.get("installDate", ""),
        "createdAt": row.get("created_at").isoformat() if row.get("created_at") else "",
        "updatedAt": row.get("updated_at").isoformat() if row.get("updated_at") else "",
    }


def _persist_system_row(usuario_id: int, system_data: dict) -> dict:
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO sistemas_instalados (usuario_id, system, created_at, updated_at)
            VALUES (%s, %s::jsonb, NOW(), NOW())
            ON CONFLICT (usuario_id)
            DO UPDATE SET system = EXCLUDED.system,
                          updated_at = NOW()
            RETURNING id, usuario_id, system, created_at, updated_at
            """,
            (usuario_id, json.dumps(system_data)),
        )
        return cursor.fetchone()


def assign_system(payload: SystemAssignRequest) -> dict:
    _ensure_systems_table()

    with db_cursor() as cursor:
        cursor.execute("SELECT id, nombre, email FROM usuarios WHERE LOWER(email) = LOWER(%s)", (payload.email,))
        user = cursor.fetchone()

        if not user:
            raise ValueError("El usuario no existe")

        assigned = _persist_system_row(user["id"], payload.system.model_dump())

    normalized = _normalize_system({
        **assigned,
        "nombre": user["nombre"],
        "email": user["email"],
    })

    return normalized


def save_system_for_email(email: str, system_data: dict) -> dict:
    _ensure_systems_table()

    with db_cursor() as cursor:
        cursor.execute("SELECT id, nombre, email FROM usuarios WHERE LOWER(email) = LOWER(%s)", (email,))
        user = cursor.fetchone()

        if not user:
            raise ValueError("El usuario no existe")

        assigned = _persist_system_row(user["id"], system_data)

    return _normalize_system(
        {
            **assigned,
            "nombre": user["nombre"],
            "email": user["email"],
        }
    )


def list_systems(email: str | None = None) -> list[dict]:
    _ensure_systems_table()

    with db_cursor() as cursor:
        if email:
            cursor.execute(
                """
                SELECT s.id, s.usuario_id, s.system, s.created_at, s.updated_at, u.nombre, u.email
                FROM sistemas_instalados s
                INNER JOIN usuarios u ON u.id = s.usuario_id
                WHERE LOWER(u.email) = LOWER(%s)
                ORDER BY s.updated_at DESC
                """,
                (email,),
            )
        else:
            cursor.execute(
                """
                SELECT s.id, s.usuario_id, s.system, s.created_at, s.updated_at, u.nombre, u.email
                FROM sistemas_instalados s
                INNER JOIN usuarios u ON u.id = s.usuario_id
                ORDER BY s.updated_at DESC
                """
            )

        rows = cursor.fetchall()

    return [_normalize_system(row) for row in rows]