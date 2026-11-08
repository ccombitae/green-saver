import threading
import time
from datetime import date, timedelta

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_REPEATABLE_READ
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.db.database import obtener_motor
from app.db.modelos import Usuario
from app.main import app

cliente = TestClient(app)
HOY = date.today()


@pytest.fixture(scope="module")
def datos(base_de_datos):
    with psycopg2.connect(base_de_datos) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "INSERT INTO usuarios (nombre, correo, contrasena_hash) VALUES "
            "('Ana Datos', 'ana.datos@prueba.com', '$2b$12$x'), ('Beto Datos', 'beto.datos@prueba.com', '$2b$12$y') "
            "RETURNING id"
        )
        ana, beto = [fila[0] for fila in cursor.fetchall()]
        cursor.execute(
            "INSERT INTO calculos (usuario_id, ciudad_id, consumo_mensual_kwh, paneles, cobertura_pct, ahorro_estimado_cop) "
            "SELECT %s, id, 250, 5, 98.5, 212500 FROM ciudades WHERE codigo = 'girardot' RETURNING id",
            (ana,),
        )
        calculo = cursor.fetchone()[0]
    return {"url": base_de_datos, "ana": ana, "beto": beto, "calculo": calculo}


def nueva_cotizacion(url: str, calculo: int, cliente_id: int) -> int:
    with psycopg2.connect(url) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "INSERT INTO cotizaciones (calculo_id, cliente_id, estado_id, precio_total) VALUES (%s, %s, 2, 12500000) RETURNING id",
            (calculo, cliente_id),
        )
        cotizacion = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO detalle_cotizacion (cotizacion_id, equipo_id, cantidad, precio_unitario_cop) "
            "SELECT %s, id, CASE WHEN nombre LIKE 'Mono%%' THEN 5 ELSE 1 END, precio_referencia_cop FROM equipos "
            "WHERE nombre IN ('Monocristalino 550W', 'Inversor Hibrido 5kW')",
            (cotizacion,),
        )
    return cotizacion


def ejecutar(url: str, sql: str, parametros=()):
    with psycopg2.connect(url) as conexion, conexion.cursor() as cursor:
        cursor.execute(sql, parametros)
        return cursor.fetchall() if cursor.description else None


def test_correo_debe_guardarse_normalizado(datos):
    with pytest.raises(psycopg2.errors.CheckViolation):
        ejecutar(datos["url"], "INSERT INTO usuarios (nombre, correo, contrasena_hash) VALUES ('X', 'Mayus@Prueba.com', 'h')")


def test_llave_foranea_rechaza_ciudad_inexistente(datos):
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        ejecutar(
            datos["url"],
            "INSERT INTO calculos (usuario_id, ciudad_id, consumo_mensual_kwh, paneles, cobertura_pct, ahorro_estimado_cop) "
            "VALUES (%s, 99999, 100, 1, 50, 1000)",
            (datos["ana"],),
        )


def test_check_rechaza_valores_negativos(datos):
    with pytest.raises(psycopg2.errors.CheckViolation):
        ejecutar(
            datos["url"],
            "INSERT INTO calculos (usuario_id, consumo_mensual_kwh, paneles, cobertura_pct, ahorro_estimado_cop) VALUES (%s, -5, 1, 1, 1)",
            (datos["ana"],),
        )


def test_trigger_audita_cada_cambio_de_estado(datos):
    cotizacion = nueva_cotizacion(datos["url"], datos["calculo"], datos["ana"])
    ejecutar(datos["url"], "UPDATE cotizaciones SET estado_id = 3 WHERE id = %s", (cotizacion,))
    filas = ejecutar(
        datos["url"],
        "SELECT estado_anterior, estado_nuevo FROM auditoria_cotizaciones WHERE cotizacion_id = %s ORDER BY id",
        (cotizacion,),
    )
    assert filas == [(None, "sent"), ("sent", "failed")]


def test_trigger_exige_fecha_al_aceptar(datos):
    cotizacion = nueva_cotizacion(datos["url"], datos["calculo"], datos["ana"])
    with pytest.raises(psycopg2.errors.CheckViolation, match="fecha de instalación"):
        ejecutar(datos["url"], "UPDATE cotizaciones SET estado_id = 4 WHERE id = %s", (cotizacion,))


def test_trigger_rechaza_fecha_anterior_al_envio(datos):
    cotizacion = nueva_cotizacion(datos["url"], datos["calculo"], datos["ana"])
    with pytest.raises(psycopg2.errors.CheckViolation, match="anterior al envío"):
        ejecutar(
            datos["url"],
            "UPDATE cotizaciones SET estado_id = 4, fecha_instalacion = %s WHERE id = %s",
            (HOY - timedelta(days=30), cotizacion),
        )


def test_procedimiento_acepta_y_crea_el_sistema(datos):
    cotizacion = nueva_cotizacion(datos["url"], datos["calculo"], datos["ana"])
    sistema = ejecutar(datos["url"], "CALL aceptar_cotizacion(%s, %s, NULL)", (cotizacion, HOY + timedelta(days=7)))[0][0]
    estado, aceptada = ejecutar(
        datos["url"],
        "SELECT e.codigo, c.aceptada_en IS NOT NULL FROM cotizaciones c JOIN estados_cotizacion e ON e.id = c.estado_id WHERE c.id = %s",
        (cotizacion,),
    )[0]
    assert (estado, aceptada) == ("accepted", True)
    potencia, origen = ejecutar(datos["url"], "SELECT potencia_kwp, cotizacion_id FROM sistemas_instalados WHERE id = %s", (sistema,))[0]
    assert float(potencia) == 2.75 and origen == cotizacion
    equipos = ejecutar(
        datos["url"],
        "SELECT e.nombre, s.cantidad FROM equipos_sistema s JOIN equipos e ON e.id = s.equipo_id WHERE s.sistema_id = %s ORDER BY e.nombre",
        (sistema,),
    )
    assert equipos == [("Inversor Hibrido 5kW", 1), ("Monocristalino 550W", 5)]


def test_procedimiento_no_acepta_dos_veces(datos):
    cotizacion = nueva_cotizacion(datos["url"], datos["calculo"], datos["ana"])
    ejecutar(datos["url"], "CALL aceptar_cotizacion(%s, %s, NULL)", (cotizacion, HOY))
    with pytest.raises(psycopg2.errors.InvalidParameterValue, match="ya fue aceptada"):
        ejecutar(datos["url"], "CALL aceptar_cotizacion(%s, %s, NULL)", (cotizacion, HOY))


def test_procedimiento_revierte_todo_si_algo_falla(datos):
    cotizacion = nueva_cotizacion(datos["url"], datos["calculo"], datos["beto"])
    with pytest.raises(psycopg2.errors.CheckViolation, match="No se pudo aceptar"):
        ejecutar(datos["url"], "CALL aceptar_cotizacion(%s, %s, NULL)", (cotizacion, HOY - timedelta(days=30)))
    assert ejecutar(datos["url"], "SELECT estado_id FROM cotizaciones WHERE id = %s", (cotizacion,)) == [(2,)]
    assert ejecutar(datos["url"], "SELECT count(*) FROM sistemas_instalados WHERE usuario_id = %s", (datos["beto"],)) == [(0,)]


def test_concurrencia_dos_administradores_aceptan_la_misma_cotizacion(datos):
    cotizacion = nueva_cotizacion(datos["url"], datos["calculo"], datos["beto"])
    primera = psycopg2.connect(datos["url"])
    segunda = psycopg2.connect(datos["url"])
    resultado = {}

    def aceptar_en_paralelo():
        try:
            with segunda.cursor() as cursor:
                cursor.execute("CALL aceptar_cotizacion(%s, %s, NULL)", (cotizacion, HOY))
            segunda.commit()
            resultado["segunda"] = "aceptada"
        except psycopg2.Error as error:
            segunda.rollback()
            resultado["segunda"] = error.diag.message_primary

    try:
        with primera.cursor() as cursor:
            cursor.execute("CALL aceptar_cotizacion(%s, %s, NULL)", (cotizacion, HOY))
        hilo = threading.Thread(target=aceptar_en_paralelo)
        hilo.start()
        time.sleep(0.5)
        assert hilo.is_alive()
        primera.commit()
        hilo.join(timeout=10)
    finally:
        primera.close()
        segunda.close()

    assert "ya fue aceptada" in resultado["segunda"]
    assert ejecutar(datos["url"], "SELECT count(*) FROM auditoria_cotizaciones WHERE cotizacion_id = %s AND estado_nuevo = 'accepted'", (cotizacion,)) == [(1,)]


def test_bloqueo_optimista_detecta_actualizacion_perdida(datos):
    motor = obtener_motor()
    with Session(motor) as sesion_a, Session(motor) as sesion_b:
        usuario_a = sesion_a.scalar(select(Usuario).where(Usuario.id == datos["ana"]))
        usuario_b = sesion_b.scalar(select(Usuario).where(Usuario.id == datos["ana"]))
        usuario_a.consumo_mensual_kwh = 300
        sesion_a.commit()
        usuario_b.consumo_mensual_kwh = 400
        with pytest.raises(StaleDataError):
            sesion_b.commit()
    assert ejecutar(datos["url"], "SELECT consumo_mensual_kwh FROM usuarios WHERE id = %s", (datos["ana"],)) == [(300,)]


def test_api_responde_409_con_version_vieja(datos):
    from app.services.servicio_autenticacion import CONTRASENA_ADMINISTRADOR, CORREO_ADMINISTRADOR

    token = cliente.post("/auth/login", json={"email": CORREO_ADMINISTRADOR, "password": CONTRASENA_ADMINISTRADOR}).json()["access_token"]
    cabecera = {"Authorization": f"Bearer {token}"}
    actual = next(u for u in cliente.get("/usuarios", headers=cabecera).json() if u["id"] == datos["beto"])
    parametros = {"nombre": "Beto Editado", "consumo_mensual": 180, "ciudad": "Girardot", "version": actual["version"]}
    primera = cliente.put(f"/usuarios/{datos['beto']}", params=parametros, headers=cabecera)
    assert primera.status_code == 200 and primera.json()["ciudad"] == "Girardot"
    segunda = cliente.put(f"/usuarios/{datos['beto']}", params=parametros, headers=cabecera)
    assert segunda.status_code == 409


def test_lectura_no_repetible_segun_nivel_de_aislamiento(datos):
    def leer_dos_veces(nivel):
        lectora = psycopg2.connect(datos["url"])
        lectora.set_isolation_level(nivel)
        try:
            with lectora.cursor() as cursor:
                cursor.execute("SELECT nombre FROM usuarios WHERE id = %s", (datos["ana"],))
                antes = cursor.fetchone()[0]
                ejecutar(datos["url"], "UPDATE usuarios SET nombre = nombre || '+' WHERE id = %s", (datos["ana"],))
                cursor.execute("SELECT nombre FROM usuarios WHERE id = %s", (datos["ana"],))
                despues = cursor.fetchone()[0]
            lectora.commit()
            return antes, despues
        finally:
            lectora.close()

    antes, despues = leer_dos_veces(ISOLATION_LEVEL_READ_COMMITTED)
    assert antes != despues
    antes, despues = leer_dos_veces(ISOLATION_LEVEL_REPEATABLE_READ)
    assert antes == despues


def test_cotizacion_con_equipo_inexistente_no_deja_nada_a_medias(datos):
    from app.services.servicio_autenticacion import CONTRASENA_ADMINISTRADOR, CORREO_ADMINISTRADOR

    token = cliente.post("/auth/login", json={"email": CORREO_ADMINISTRADOR, "password": CONTRASENA_ADMINISTRADOR}).json()["access_token"]
    antes = ejecutar(datos["url"], "SELECT count(*) FROM cotizaciones")[0][0]
    respuesta = cliente.post(
        "/quotes/send",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "calculationId": datos["calculo"],
            "clientEmail": "ana.datos@prueba.com",
            "totalPrice": 100,
            "materials": {
                "panelType": "Monocristalino 550W",
                "inverterType": "Inversor que no existe",
                "batteryType": "Sin bateria",
                "structureType": "Estructura coplanar aluminio",
            },
        },
    )
    assert respuesta.status_code == 400
    assert ejecutar(datos["url"], "SELECT count(*) FROM cotizaciones")[0][0] == antes


def test_funcion_de_estadisticas_mensuales(datos):
    filas = ejecutar(datos["url"], "SELECT * FROM fn_estadisticas_mensuales(%s, %s)", (HOY - timedelta(days=31), HOY))
    assert sum(f[1] for f in filas) >= 1


def test_postgresql_no_permite_lecturas_sucias(datos):
    escritora = psycopg2.connect(datos["url"])
    lectora = psycopg2.connect(datos["url"])
    lectora.set_session(isolation_level="READ UNCOMMITTED")
    try:
        with escritora.cursor() as cursor:
            cursor.execute("SELECT nombre FROM usuarios WHERE id = %s", (datos["beto"],))
            original = cursor.fetchone()[0]
            cursor.execute("UPDATE usuarios SET nombre = 'Cambio sin confirmar' WHERE id = %s", (datos["beto"],))
        with lectora.cursor() as cursor:
            cursor.execute("SELECT nombre FROM usuarios WHERE id = %s", (datos["beto"],))
            leido = cursor.fetchone()[0]
        escritora.rollback()
    finally:
        escritora.close()
        lectora.close()
    assert leido == original


def test_interbloqueo_es_detectado_y_una_transaccion_es_victima(datos):
    primera = psycopg2.connect(datos["url"])
    segunda = psycopg2.connect(datos["url"])
    errores = []

    def actualizar(conexion, orden):
        try:
            with conexion.cursor() as cursor:
                cursor.execute("UPDATE usuarios SET consumo_mensual_kwh = consumo_mensual_kwh + 1 WHERE id = %s", (orden[0],))
                time.sleep(0.4)
                cursor.execute("UPDATE usuarios SET consumo_mensual_kwh = consumo_mensual_kwh + 1 WHERE id = %s", (orden[1],))
            conexion.commit()
        except psycopg2.errors.DeadlockDetected as error:
            conexion.rollback()
            errores.append(error.pgcode)

    try:
        hilos = [
            threading.Thread(target=actualizar, args=(primera, (datos["ana"], datos["beto"]))),
            threading.Thread(target=actualizar, args=(segunda, (datos["beto"], datos["ana"]))),
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=15)
    finally:
        primera.close()
        segunda.close()
    assert errores == ["40P01"]


def test_la_aplicacion_reintenta_despues_de_un_interbloqueo():
    from sqlalchemy.exc import DBAPIError

    from app.db.database import ejecutar_con_reintentos

    class ErrorDelMotor(Exception):
        pgcode = "40P01"

    intentos = []

    def operacion():
        intentos.append(1)
        if len(intentos) == 1:
            raise DBAPIError("UPDATE usuarios ...", {}, ErrorDelMotor("deadlock detected"))
        return "confirmada"

    assert ejecutar_con_reintentos(operacion, espera_inicial=0) == "confirmada"
    assert len(intentos) == 2


def test_un_error_que_no_es_de_concurrencia_no_se_reintenta():
    from sqlalchemy.exc import DBAPIError

    from app.db.database import ejecutar_con_reintentos

    class ErrorDelMotor(Exception):
        pgcode = "23514"

    intentos = []

    def operacion():
        intentos.append(1)
        raise DBAPIError("INSERT ...", {}, ErrorDelMotor("check violation"))

    with pytest.raises(DBAPIError):
        ejecutar_con_reintentos(operacion, espera_inicial=0)
    assert len(intentos) == 1


def test_veinte_administradores_aceptan_la_misma_cotizacion_al_tiempo(datos):
    from app.services.servicio_cotizaciones import aceptar_cotizacion

    cotizacion = nueva_cotizacion(datos["url"], datos["calculo"], datos["beto"])
    resultados = []
    salida = threading.Barrier(20)

    def administrador():
        salida.wait()
        try:
            aceptar_cotizacion(cotizacion, HOY.isoformat())
            resultados.append("aceptada")
        except ValueError as error:
            resultados.append(str(error))

    hilos = [threading.Thread(target=administrador) for _ in range(20)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)
    assert resultados.count("aceptada") == 1
    assert sum("ya fue aceptada" in r for r in resultados) == 19
    assert ejecutar(datos["url"], "SELECT count(*) FROM auditoria_cotizaciones WHERE cotizacion_id = %s AND estado_nuevo = 'accepted'", (cotizacion,)) == [(1,)]
