from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import settings

_motores: dict[str, Engine] = {}


def normalizar_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def obtener_motor() -> Engine:
    url = settings.database_url
    if not url:
        raise RuntimeError("DATABASE_URL no configurada")
    if url not in _motores:
        _motores[url] = create_engine(
            normalizar_url(url),
            pool_size=5,
            max_overflow=5,
            pool_timeout=10,
            pool_recycle=1800,
            pool_pre_ping=True,
        )
    return _motores[url]


@contextmanager
def sesion_transaccional():
    with Session(obtener_motor(), expire_on_commit=False) as sesion:
        with sesion.begin():
            yield sesion


@contextmanager
def sesion_lectura():
    with Session(obtener_motor(), expire_on_commit=False) as sesion:
        yield sesion
