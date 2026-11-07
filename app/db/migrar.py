import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import settings
from app.db.database import normalizar_url, obtener_motor

registro = logging.getLogger("green_saver.migraciones")
CARPETA_MIGRACIONES = Path(__file__).with_name("migraciones")
LLAVE_BLOQUEO = 7_310_455


def configuracion_alembic(url: str | None = None) -> Config:
    configuracion = Config()
    configuracion.set_main_option("script_location", str(CARPETA_MIGRACIONES))
    configuracion.set_main_option("path_separator", "os")
    configuracion.set_main_option("version_locations", str(CARPETA_MIGRACIONES / "versiones"))
    configuracion.set_main_option("sqlalchemy.url", normalizar_url(url or settings.database_url).replace("%", "%%"))
    return configuracion


def aplicar_migraciones(destino: str = "head") -> None:
    configuracion = configuracion_alembic()
    with obtener_motor().connect() as conexion:
        conexion.execute(text("SELECT pg_advisory_lock(:llave)"), {"llave": LLAVE_BLOQUEO})
        conexion.commit()
        try:
            configuracion.attributes["conexion"] = conexion
            command.upgrade(configuracion, destino)
            conexion.commit()
        finally:
            conexion.execute(text("SELECT pg_advisory_unlock(:llave)"), {"llave": LLAVE_BLOQUEO})
            conexion.commit()


def migrar_si_esta_habilitado() -> None:
    if os.getenv("INIT_DB", "false").lower() != "true":
        return
    try:
        aplicar_migraciones()
        registro.info("Base de datos en la última migración")
    except Exception as error:
        registro.error("No se pudieron aplicar las migraciones: %s", error)
