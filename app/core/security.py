from datetime import datetime, timedelta, timezone

from fastapi import status
from jose import JWTError, jwt

from app.core.config import settings


ALGORITHM = "HS256"


def _build_token_payload(user: dict, token_type: str, expires_delta: timedelta) -> dict:
    now = datetime.now(timezone.utc)

    return {
        "sub": str(user["id"]),
        "email": user["email"],
        "name": user.get("name") or "Usuario",
        "phone": user.get("phone"),
        "role": user.get("role", "user"),
        "token_type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }


def create_access_token(user: dict) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    payload = _build_token_payload(user, "access", expires_delta)
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return token, int(expires_delta.total_seconds())


def create_refresh_token(user: dict) -> tuple[str, int]:
    expires_delta = timedelta(days=settings.refresh_token_expire_days)
    payload = _build_token_payload(user, "refresh", expires_delta)
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return token, int(expires_delta.total_seconds())


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Token invalido") from exc


def extract_bearer_token(authorization_header: str | None) -> str:
    if not authorization_header:
        raise ValueError("Falta el token de autorizacion")

    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ValueError("Formato de token invalido")

    return token.strip()


def decode_bearer_token(authorization_header: str | None) -> dict:
    return decode_token(extract_bearer_token(authorization_header))


def is_admin_role(role: str | None) -> bool:
    return (role or "").strip().lower() == "admin"


def unauthorized_response(message: str = "No autenticado") -> tuple[dict, int]:
    return {"detail": message}, status.HTTP_401_UNAUTHORIZED


def forbidden_response(message: str = "No tienes permisos para acceder a este recurso") -> tuple[dict, int]:
    return {"detail": message}, status.HTTP_403_FORBIDDEN