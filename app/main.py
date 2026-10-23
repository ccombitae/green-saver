import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.db.init_db import init_db_if_enabled
from app.core.security import decode_bearer_token, forbidden_response, is_admin_role, unauthorized_response
from app.routes.auth import router as auth_router
from app.routes.ml import router as ml_router
from app.routes.quotes import router as quotes_router
from app.routes.systems import router as systems_router
from app.routes.solar import router as solar_router
from app.routes.users import router as users_router


app = FastAPI(title=settings.app_name, version=settings.app_version)

log = logging.getLogger("green_saver")


@app.exception_handler(StarletteHTTPException)
async def ocultar_errores_internos(request: Request, exc: StarletteHTTPException):
    """Los errores 5xx no deben mostrar detalles internos (servidor de BD, SQL…)."""
    if exc.status_code >= 500:
        log.error("Error interno en %s %s: %s", request.method, request.url.path, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": "Ocurrió un error en el servidor. Intenta de nuevo en unos minutos."},
        )
    return await http_exception_handler(request, exc)



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
    "/systems",
)

ADMIN_ONLY_PREFIXES = (
    "/usuarios",
    "/quotes",
    "/calculos/reporte",
    "/systems/assign",
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

# CORS se registra DESPUÉS del middleware de autenticación para que quede como
# capa externa: así las respuestas 401/403 también llevan los encabezados CORS
# y el navegador puede leerlas (por ejemplo, para renovar la sesión).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(solar_router)
app.include_router(quotes_router)
app.include_router(systems_router)
app.include_router(ml_router)


@app.on_event("startup")
def crear_tablas():
    init_db_if_enabled()


@app.get("/")
async def root():
    return {
        "message": settings.welcome_message,
        "version": settings.app_version,
        "docs": "/docs",
    }
