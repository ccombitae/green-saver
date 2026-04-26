from datetime import datetime

from app.db.database import db_cursor
from app.schemas.auth import PasswordRecoveryRequest, UsuarioLogin, UsuarioRegistro


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _display_name(email: str) -> str:
    local_part = email.split("@")[0]
    pieces = local_part.replace(".", " ").replace("_", " ").replace("-", " ").split()
    return " ".join(piece.capitalize() for piece in pieces) or "Usuario"


def register_user(payload: UsuarioRegistro) -> dict:
    email = _normalize_email(payload.email)
    name = payload.name.strip()
    phone = payload.phone.strip()
    role = payload.role.strip() or "user"

    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM usuarios WHERE LOWER(email) = LOWER(%s)", (email,))
        if cursor.fetchone():
            raise ValueError("El usuario ya existe")

        cursor.execute(
            """
            INSERT INTO usuarios (nombre, email, telefono, password, rol, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING id
            """,
            (name, email, phone, payload.password, role),
        )
        user_id = cursor.fetchone()["id"]

    return {
        "id": user_id,
        "email": email,
        "name": name,
        "phone": phone,
        "role": role,
        "token": None,
    }


def login_user(payload: UsuarioLogin) -> dict:
    email = _normalize_email(payload.email)

    with db_cursor() as cursor:
        cursor.execute(
            "SELECT id, nombre, email, telefono, rol FROM usuarios WHERE LOWER(email) = LOWER(%s) AND password = %s",
            (email, payload.password),
        )
        user = cursor.fetchone()

    if not user:
        raise ValueError("Credenciales incorrectas")

    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["nombre"] or _display_name(user["email"]),
        "phone": user["telefono"],
        "role": user["rol"],
        "token": None,
    }


def get_current_user(email: str) -> dict:
    normalized_email = _normalize_email(email)

    with db_cursor() as cursor:
        cursor.execute(
            "SELECT id, nombre, email, telefono, rol FROM usuarios WHERE LOWER(email) = LOWER(%s)",
            (normalized_email,),
        )
        user = cursor.fetchone()

    if not user:
        raise ValueError("Usuario no encontrado")

    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["nombre"] or _display_name(user["email"]),
        "phone": user["telefono"],
        "role": user["rol"],
    }


def recover_password(payload: PasswordRecoveryRequest) -> dict:
    email = _normalize_email(payload.email)
    new_password = payload.newPassword.strip()

    if email == "admin@greensaver.com":
        raise ValueError("La contraseña del administrador fijo no se puede recuperar desde esta pantalla")

    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM usuarios WHERE LOWER(email) = LOWER(%s)", (email,))
        existing = cursor.fetchone()
        if not existing:
            raise ValueError("No existe una cuenta registrada con ese correo")

        cursor.execute(
            "UPDATE usuarios SET password = %s, updated_at = NOW() WHERE LOWER(email) = LOWER(%s)",
            (new_password, email),
        )

    return {"message": "Contraseña actualizada", "email": email}
