from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
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
