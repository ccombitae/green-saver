from fastapi import APIRouter, HTTPException

from fastapi import Request

from app.schemas.auth import AuthResponse, PasswordRecoveryRequest, RefreshTokenRequest, UsuarioLogin, UsuarioRegistro
from app.services.auth_service import get_current_user, login_user, recover_password, refresh_session, register_user


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(user: UsuarioRegistro):
    try:
        return register_user(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/login", response_model=AuthResponse)
async def login(credentials: UsuarioLogin):
    try:
        return login_user(credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/me")
async def current_user(request: Request, email: str | None = None):
    try:
        token_payload = getattr(request.state, "auth", None)
        return get_current_user(email=email, token_payload=token_payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/refresh", response_model=AuthResponse)
async def refresh_tokens(payload: RefreshTokenRequest):
    try:
        return refresh_session(payload)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/recover-password")
async def recover_user_password(payload: PasswordRecoveryRequest):
    try:
        return recover_password(payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 400 if "administrador" in detail.lower() else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
