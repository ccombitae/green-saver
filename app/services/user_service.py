from app.db.database import db_cursor
from app.schemas.users import UsuarioCreate, UsuarioUpdate


def list_users() -> list[dict]:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, nombre, email, telefono, rol, ciudad, consumo_mensual, created_at, updated_at
            FROM usuarios
            ORDER BY created_at DESC
            """
        )
        return cursor.fetchall()


def create_user(nombre: str, ciudad: str, consumo_mensual: float) -> dict:
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO usuarios (nombre, ciudad, consumo_mensual, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            RETURNING id
            """,
            (nombre, ciudad, consumo_mensual),
        )
        created = cursor.fetchone()

    return {"message": "Usuario insertado", "id": created["id"]}


def update_user(user_id: int, nombre: str, ciudad: str, consumo_mensual: float) -> dict:
    with db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE usuarios
            SET nombre = %s,
                ciudad = %s,
                consumo_mensual = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (nombre, ciudad, consumo_mensual, user_id),
        )

    return {"message": "Usuario actualizado"}


def delete_user(user_id: int) -> dict:
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))

    return {"message": "Usuario eliminado"}
