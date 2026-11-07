import sys
import threading
import time
from datetime import date

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_REPEATABLE_READ

INICIO = time.perf_counter()


def decir(sesion: str, texto: str) -> None:
    print(f"[{time.perf_counter() - INICIO:5.2f} s] {sesion:<9} {texto}", flush=True)


def preparar(url: str) -> dict:
    with psycopg2.connect(url) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "INSERT INTO usuarios (nombre, correo, contrasena_hash, consumo_mensual_kwh) "
            "VALUES ('Demo Concurrencia', 'demo.concurrencia@prueba.com', '$2b$12$demo', 100) "
            "ON CONFLICT (correo) DO UPDATE SET consumo_mensual_kwh = 100 RETURNING id"
        )
        usuario = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO calculos (usuario_id, consumo_mensual_kwh, paneles, cobertura_pct, ahorro_estimado_cop) "
            "VALUES (%s, 250, 5, 98, 212500) RETURNING id",
            (usuario,),
        )
        calculo = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO cotizaciones (calculo_id, cliente_id, estado_id, precio_total) VALUES (%s, %s, 2, 12500000) RETURNING id",
            (calculo, usuario),
        )
        cotizacion = cursor.fetchone()[0]
    return {"usuario": usuario, "cotizacion": cotizacion}


def actualizacion_perdida(url: str, usuario: int, bloquear: bool) -> None:
    titulo = "CON SELECT ... FOR UPDATE" if bloquear else "SIN BLOQUEO"
    print(f"\n=== 1. Dos sesiones suman 50 kWh al mismo usuario ({titulo}) ===")
    with psycopg2.connect(url) as conexion, conexion.cursor() as cursor:
        cursor.execute("UPDATE usuarios SET consumo_mensual_kwh = 100 WHERE id = %s", (usuario,))
    lectura = "SELECT consumo_mensual_kwh FROM usuarios WHERE id = %s" + (" FOR UPDATE" if bloquear else "")
    listo = threading.Event()

    def sesion(nombre: str, espera: float) -> None:
        conexion = psycopg2.connect(url)
        try:
            with conexion.cursor() as cursor:
                time.sleep(espera)
                cursor.execute(lectura, (usuario,))
                valor = cursor.fetchone()[0]
                decir(nombre, f"lee consumo = {valor}")
                if nombre == "Sesión A":
                    listo.set()
                    time.sleep(0.6)
                cursor.execute("UPDATE usuarios SET consumo_mensual_kwh = %s WHERE id = %s", (valor + 50, usuario))
                conexion.commit()
                decir(nombre, f"escribe {valor + 50} y hace COMMIT")
        finally:
            conexion.close()

    a = threading.Thread(target=sesion, args=("Sesión A", 0))
    a.start()
    listo.wait()
    b = threading.Thread(target=sesion, args=("Sesión B", 0.1))
    b.start()
    a.join()
    b.join()
    with psycopg2.connect(url) as conexion, conexion.cursor() as cursor:
        cursor.execute("SELECT consumo_mensual_kwh FROM usuarios WHERE id = %s", (usuario,))
        final = cursor.fetchone()[0]
    estado = "correcto" if final == 200 else "¡se perdió una actualización!"
    print(f"Resultado final: {final} (esperado 200) -> {estado}")


def aceptar_en_paralelo(url: str, cotizacion: int) -> None:
    print("\n=== 2. Dos administradores aceptan la misma cotización (procedimiento con FOR UPDATE) ===")
    primera, segunda = psycopg2.connect(url), psycopg2.connect(url)

    def administrador_b() -> None:
        try:
            decir("Admin B", "CALL aceptar_cotizacion(...) -> espera el bloqueo de la fila")
            with segunda.cursor() as cursor:
                cursor.execute("CALL aceptar_cotizacion(%s, %s, NULL)", (cotizacion, date.today()))
            segunda.commit()
            decir("Admin B", "aceptó la cotización")
        except psycopg2.Error as error:
            segunda.rollback()
            decir("Admin B", f"ERROR -> {error.diag.message_primary} (ROLLBACK)")

    try:
        with primera.cursor() as cursor:
            cursor.execute("CALL aceptar_cotizacion(%s, %s, NULL)", (cotizacion, date.today()))
        decir("Admin A", "aceptó la cotización (transacción abierta, fila bloqueada)")
        hilo = threading.Thread(target=administrador_b)
        hilo.start()
        time.sleep(1)
        primera.commit()
        decir("Admin A", "COMMIT -> libera el bloqueo")
        hilo.join()
    finally:
        primera.close()
        segunda.close()
    with psycopg2.connect(url) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "SELECT estado_anterior, estado_nuevo FROM auditoria_cotizaciones WHERE cotizacion_id = %s ORDER BY id", (cotizacion,)
        )
        print("Auditoría (trigger):", cursor.fetchall())


def niveles_de_aislamiento(url: str, usuario: int) -> None:
    print("\n=== 3. Lectura no repetible según el nivel de aislamiento ===")
    for nombre, nivel in (("READ COMMITTED", ISOLATION_LEVEL_READ_COMMITTED), ("REPEATABLE READ", ISOLATION_LEVEL_REPEATABLE_READ)):
        lectora = psycopg2.connect(url)
        lectora.set_isolation_level(nivel)
        with lectora.cursor() as cursor:
            cursor.execute("SELECT consumo_mensual_kwh FROM usuarios WHERE id = %s", (usuario,))
            antes = cursor.fetchone()[0]
            with psycopg2.connect(url) as otra, otra.cursor() as escritora:
                escritora.execute("UPDATE usuarios SET consumo_mensual_kwh = consumo_mensual_kwh + 1 WHERE id = %s", (usuario,))
            cursor.execute("SELECT consumo_mensual_kwh FROM usuarios WHERE id = %s", (usuario,))
            despues = cursor.fetchone()[0]
        lectora.commit()
        lectora.close()
        print(f"{nombre:<16} primera lectura = {antes}, segunda lectura = {despues} -> "
              f"{'lectura no repetible' if antes != despues else 'la transacción ve una foto estable'}")


def main(url: str) -> None:
    datos = preparar(url)
    actualizacion_perdida(url, datos["usuario"], bloquear=False)
    actualizacion_perdida(url, datos["usuario"], bloquear=True)
    aceptar_en_paralelo(url, datos["cotizacion"])
    niveles_de_aislamiento(url, datos["usuario"])


if __name__ == "__main__":
    main(sys.argv[1])
