from passlib.context import CryptContext

from app.core.security import create_access_token, create_refresh_token, decode_token
from app.db.database import db_cursor
from app.schemas.auth import PasswordRecoveryRequest, RefreshTokenRequest, UsuarioLogin, UsuarioRegistro


pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")
ADMIN_EMAIL = "admin@greensaver.com"
ADMIN_PASSWORD = "admin"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _display_name(email: str) -> str:
    local_part = email.split("@")[0]
    pieces = local_part.replace(".", " ").replace("_", " ").replace("-", " ").split()
    return " ".join(piece.capitalize() for piece in pieces) or "Usuario"


def _admin_user() -> dict:
    return {
        "id": 0,
        "email": ADMIN_EMAIL,
        "name": "Administrador",
        "phone": None,
        "role": "admin",
    }


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain_password: str, stored_password: str) -> bool:
    if not stored_password:
        return False

    if stored_password.startswith("$2"):
        try:
            return pwd_context.verify(plain_password, stored_password)
        except Exception:
            return False

    return plain_password == stored_password


def _issue_tokens(user: dict) -> dict:
    access_token, expires_in = create_access_token(user)
    refresh_token, refresh_expires_in = create_refresh_token(user)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "refresh_expires_in": refresh_expires_in,
    }


def _user_response(user: dict) -> dict:
    token_data = _issue_tokens(user)

    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "phone": user.get("phone"),
        "role": user["role"],
        **token_data,
    }


def register_user(payload: UsuarioRegistro) -> dict:
    email = _normalize_email(payload.email)
    name = payload.name.strip()
    phone = payload.phone.strip()
    role = payload.role.strip() or "user"
    hashed_password = _hash_password(payload.password)

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
            (name, email, phone, hashed_password, role),
        )
        user_id = cursor.fetchone()["id"]

    user = {
        "id": user_id,
        "email": email,
        "name": name,
        "phone": phone,
        "role": role,
    }

    return _user_response(user)


def login_user(payload: UsuarioLogin) -> dict:
    email = _normalize_email(payload.email)

    if email == ADMIN_EMAIL and payload.password == ADMIN_PASSWORD:
        return _user_response(_admin_user())

    with db_cursor() as cursor:
        cursor.execute(
            "SELECT id, nombre, email, telefono, rol, password FROM usuarios WHERE LOWER(email) = LOWER(%s)",
            (email,),
        )
        user = cursor.fetchone()

    if not user or not _verify_password(payload.password, user.get("password", "")):
        raise ValueError("Credenciales incorrectas")

    user_data = {
        "id": user["id"],
        "email": user["email"],
        "name": user["nombre"] or _display_name(user["email"]),
        "phone": user.get("telefono"),
        "role": user["rol"],
    }

    return _user_response(user_data)


def get_current_user(email: str | None = None, token_payload: dict | None = None) -> dict:
    normalized_email = _normalize_email(token_payload.get("email") if token_payload else email or "")

    if normalized_email == ADMIN_EMAIL:
        return _admin_user()

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


def refresh_session(payload: RefreshTokenRequest) -> dict:
    claims = decode_token(payload.refreshToken)

    if claims.get("token_type") != "refresh":
        raise ValueError("Token de refresco invalido")

    if _normalize_email(claims.get("email", "")) == ADMIN_EMAIL:
        return _user_response(_admin_user())

    user = get_current_user(email=claims.get("email"))
    return _user_response(user)


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
            (_hash_password(new_password), email),
        )

    return {"message": "Contraseña actualizada", "email": email}
