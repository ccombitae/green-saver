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


def lectura_sucia(url: str, usuario: int) -> None:
    print("\n=== 4. Lectura sucia: otra sesión intenta leer un cambio sin COMMIT ===")
    escritora, lectora = psycopg2.connect(url), psycopg2.connect(url)
    lectora.set_session(isolation_level="READ UNCOMMITTED")
    try:
        with escritora.cursor() as cursor:
            cursor.execute("UPDATE usuarios SET consumo_mensual_kwh = 0 WHERE id = %s", (usuario,))
        decir("Sesión A", "UPDATE consumo = 0 (todavía sin COMMIT)")
        with lectora.cursor() as cursor:
            cursor.execute("SELECT consumo_mensual_kwh FROM usuarios WHERE id = %s", (usuario,))
            decir("Sesión B", f"READ UNCOMMITTED lee consumo = {cursor.fetchone()[0]} (no ve el 0)")
        escritora.rollback()
        decir("Sesión A", "ROLLBACK: el 0 nunca existió")
    finally:
        escritora.close()
        lectora.close()
    print("PostgreSQL no permite lecturas sucias: READ UNCOMMITTED se comporta como READ COMMITTED.")


def interbloqueo(url: str, usuario: int, otro: int) -> None:
    print("\n=== 5. Interbloqueo (deadlock): dos sesiones bloquean filas en orden contrario ===")

    def sesion(nombre: str, orden: tuple[int, int]) -> None:
        conexion = psycopg2.connect(url)
        try:
            with conexion.cursor() as cursor:
                cursor.execute("UPDATE usuarios SET consumo_mensual_kwh = consumo_mensual_kwh + 1 WHERE id = %s", (orden[0],))
                decir(nombre, f"bloquea el usuario {orden[0]}")
                time.sleep(0.5)
                decir(nombre, f"pide el usuario {orden[1]}")
                cursor.execute("UPDATE usuarios SET consumo_mensual_kwh = consumo_mensual_kwh + 1 WHERE id = %s", (orden[1],))
            conexion.commit()
            decir(nombre, "COMMIT")
        except psycopg2.errors.DeadlockDetected:
            conexion.rollback()
            decir(nombre, "ERROR 40P01 deadlock detected -> es la víctima (ROLLBACK); la API reintenta")
        finally:
            conexion.close()

    hilos = [threading.Thread(target=sesion, args=("Sesión A", (usuario, otro))),
             threading.Thread(target=sesion, args=("Sesión B", (otro, usuario)))]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()


def carga_concurrente(url: str, usuario: int) -> None:
    print("\n=== 6. Veinte administradores aceptan la misma cotización al mismo tiempo ===")
    with psycopg2.connect(url) as conexion, conexion.cursor() as cursor:
        cursor.execute("SELECT id FROM calculos WHERE usuario_id = %s LIMIT 1", (usuario,))
        calculo = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO cotizaciones (calculo_id, cliente_id, estado_id, precio_total) VALUES (%s, %s, 2, 1) RETURNING id",
            (calculo, usuario),
        )
        cotizacion = cursor.fetchone()[0]
    resultados = []
    salida = threading.Barrier(20)

    def administrador() -> None:
        conexion = psycopg2.connect(url)
        salida.wait()
        try:
            with conexion.cursor() as cursor:
                cursor.execute("CALL aceptar_cotizacion(%s, %s, NULL)", (cotizacion, date.today()))
            conexion.commit()
            resultados.append("aceptada")
        except psycopg2.Error as error:
            conexion.rollback()
            resultados.append(error.diag.message_primary)
        finally:
            conexion.close()

    inicio = time.perf_counter()
    hilos = [threading.Thread(target=administrador) for _ in range(20)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    print(f"Aceptadas: {resultados.count('aceptada')} · rechazadas por 'ya fue aceptada': "
          f"{sum('ya fue aceptada' in r for r in resultados)} · tiempo total {time.perf_counter() - inicio:.2f} s")


def main(url: str) -> None:
    datos = preparar(url)
    actualizacion_perdida(url, datos["usuario"], bloquear=False)
    actualizacion_perdida(url, datos["usuario"], bloquear=True)
    aceptar_en_paralelo(url, datos["cotizacion"])
    niveles_de_aislamiento(url, datos["usuario"])
    lectura_sucia(url, datos["usuario"])
    with psycopg2.connect(url) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "INSERT INTO usuarios (nombre, correo, contrasena_hash) VALUES ('Demo Dos', 'demo.dos@prueba.com', '$2b$12$demo') "
            "ON CONFLICT (correo) DO UPDATE SET nombre = EXCLUDED.nombre RETURNING id"
        )
        otro = cursor.fetchone()[0]
    interbloqueo(url, datos["usuario"], otro)
    carga_concurrente(url, datos["usuario"])


if __name__ == "__main__":
    main(sys.argv[1])
