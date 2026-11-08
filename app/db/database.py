import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import TypeVar

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import settings

_motores: dict[str, Engine] = {}
registro = logging.getLogger("green_saver.bd")
Resultado = TypeVar("Resultado")
CODIGOS_REINTENTABLES = {"40P01": "interbloqueo", "40001": "fallo de serialización"}


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


def codigo_de_error(error: DBAPIError) -> str | None:
    return getattr(error.orig, "pgcode", None)


def ejecutar_con_reintentos(operacion: Callable[[], Resultado], intentos: int = 3, espera_inicial: float = 0.05) -> Resultado:
    for intento in range(1, intentos + 1):
        try:
            return operacion()
        except DBAPIError as error:
            codigo = codigo_de_error(error)
            if codigo not in CODIGOS_REINTENTABLES or intento == intentos:
                raise
            registro.warning("Transacción abortada por %s; reintento %s de %s", CODIGOS_REINTENTABLES[codigo], intento + 1, intentos)
            time.sleep(espera_inicial * 2 ** (intento - 1))
    raise RuntimeError("Sin intentos")
