import sys
import time

from sqlalchemy import event, select
from sqlalchemy.orm import Session, lazyload

from app.core.config import settings
from app.db.database import obtener_motor
from app.db.modelos import Cotizacion
from app.services.servicio_cotizaciones import a_diccionario

LIMITE = 500


def medir(opciones: list) -> tuple[int, float]:
    motor = obtener_motor()
    consultas = []

    def contar(*_):
        consultas.append(1)

    event.listen(motor, "before_cursor_execute", contar)
    try:
        inicio = time.perf_counter()
        with Session(motor) as sesion:
            cotizaciones = sesion.scalars(select(Cotizacion).options(*opciones).order_by(Cotizacion.id).limit(LIMITE)).all()
            [a_diccionario(c) for c in cotizaciones]
        return len(consultas), (time.perf_counter() - inicio) * 1000
    finally:
        event.remove(motor, "before_cursor_execute", contar)


def main(url: str) -> None:
    settings.database_url = url
    medir([])
    perezosa = medir([lazyload(Cotizacion.cliente), lazyload(Cotizacion.estado), lazyload(Cotizacion.detalle)])
    optimizada = medir([])
    print(f"Listar {LIMITE} cotizaciones con su cliente, estado y detalle")
    print(f"Carga perezosa (N+1): {perezosa[0]} consultas en {perezosa[1]:.0f} ms")
    print(f"joined + selectin:    {optimizada[0]} consultas en {optimizada[1]:.0f} ms")


if __name__ == "__main__":
    main(sys.argv[1])
