from fastapi import APIRouter, HTTPException

from fastapi import Request

from app.schemas.auth import AuthResponse, PasswordRecoveryRequest, PasswordRecoveryResponse, RefreshTokenRequest, UsuarioLogin, UsuarioRegistro
from app.services.servicio_autenticacion import iniciar_sesion, recuperar_contrasena, registrar_usuario, renovar_sesion, usuario_actual


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(user: UsuarioRegistro):
    try:
        return registrar_usuario(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/login", response_model=AuthResponse)
async def login(credentials: UsuarioLogin):
    try:
        return iniciar_sesion(credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/me")
async def current_user(request: Request, email: str | None = None):
    try:
        token_payload = getattr(request.state, "auth", None)
        return usuario_actual(correo=email, datos_token=token_payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/refresh", response_model=AuthResponse)
async def refresh_tokens(payload: RefreshTokenRequest):
    try:
        return renovar_sesion(payload)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/recover-password", response_model=PasswordRecoveryResponse)
async def recover_user_password(payload: PasswordRecoveryRequest):
    try:
        return recuperar_contrasena(payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 400 if "administrador" in detail.lower() else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
