import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.db.database import normalizar_url
from app.db.modelos import Base

configuracion = context.config
metadatos = Base.metadata


def url_base_datos() -> str:
    return normalizar_url(configuracion.get_main_option("sqlalchemy.url") or os.environ["DATABASE_URL"])


def ejecutar_sin_conexion() -> None:
    context.configure(url=url_base_datos(), target_metadata=metadatos, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def ejecutar_con_conexion() -> None:
    conexion = configuracion.attributes.get("conexion")
    if conexion is not None:
        context.configure(connection=conexion, target_metadata=metadatos)
        with context.begin_transaction():
            context.run_migrations()
        return
    motor = create_engine(url_base_datos(), poolclass=pool.NullPool)
    with motor.connect() as conexion:
        context.configure(connection=conexion, target_metadata=metadatos)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    ejecutar_sin_conexion()
else:
    ejecutar_con_conexion()
