from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.security import decode_bearer_token, forbidden_response, is_admin_role, unauthorized_response
from app.routes.auth import router as auth_router
from app.routes.quotes import router as quotes_router
from app.routes.solar import router as solar_router
from app.routes.users import router as users_router


app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/auth/login",
    "/auth/register",
    "/auth/recover-password",
}

AUTH_REQUIRED_PREFIXES = (
    "/auth/me",
    "/calculos",
    "/usuarios",
    "/quotes",
)

ADMIN_ONLY_PREFIXES = (
    "/usuarios",
    "/quotes",
    "/calculos/reporte",
)


@app.middleware("http")
async def auth_guard(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"

    if request.method == "OPTIONS" or path in PUBLIC_PATHS:
        return await call_next(request)

    requires_auth = any(path == prefix or path.startswith(f"{prefix}/") for prefix in AUTH_REQUIRED_PREFIXES)
    if not requires_auth:
        return await call_next(request)

    authorization_header = request.headers.get("Authorization")

    try:
        token_data = decode_bearer_token(authorization_header)
    except ValueError as exc:
        detail, status_code = unauthorized_response(str(exc))
        return JSONResponse(status_code=status_code, content=detail)

    request.state.auth = token_data

    requires_admin = any(path == prefix or path.startswith(f"{prefix}/") for prefix in ADMIN_ONLY_PREFIXES)
    if requires_admin and not is_admin_role(token_data.get("role")):
        detail, status_code = forbidden_response("No tienes permisos para acceder a este recurso")
        return JSONResponse(status_code=status_code, content=detail)

    return await call_next(request)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(solar_router)
app.include_router(quotes_router)


@app.get("/")
async def root():
    return {
        "message": settings.welcome_message,
        "version": settings.app_version,
        "docs": "/docs",
    }
