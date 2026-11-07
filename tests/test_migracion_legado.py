from pathlib import Path

import psycopg2
import pytest

from app.core.config import settings
from app.db.migrar import aplicar_migraciones

DATOS = Path(__file__).with_name("datos")


@pytest.fixture(scope="module")
def migrada(base_de_datos):
    with psycopg2.connect(base_de_datos) as conexion, conexion.cursor() as cursor:
        cursor.execute("DROP SCHEMA public CASCADE")
        cursor.execute("CREATE SCHEMA public")
        cursor.execute((DATOS / "esquema_legado.sql").read_text(encoding="utf-8"))
        cursor.execute((DATOS / "datos_legados.sql").read_text(encoding="utf-8"))
    settings.database_url = base_de_datos
    aplicar_migraciones()
    conexion = psycopg2.connect(base_de_datos)
    yield conexion
    conexion.close()


def consultar(conexion, sql):
    with conexion.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


def test_las_tablas_anteriores_quedan_en_el_esquema_legado(migrada):
    tablas = consultar(migrada, "SELECT table_name FROM information_schema.tables WHERE table_schema = 'legado' ORDER BY 1")
    assert [t[0] for t in tablas] == ["calculos_sistema", "cotizaciones", "sistemas_instalados", "usuarios"]


def test_los_correos_quedan_normalizados_y_con_su_ciudad(migrada):
    filas = consultar(
        migrada,
        "SELECT u.correo, c.codigo FROM usuarios u LEFT JOIN ciudades c ON c.id = u.ciudad_id WHERE u.correo LIKE '%correo.com' ORDER BY 1",
    )
    assert filas == [("ana@correo.com", "girardot"), ("luis@correo.com", None)]


def test_los_calculos_se_unen_a_su_usuario_por_correo(migrada):
    filas = consultar(migrada, "SELECT c.id, u.correo FROM calculos c LEFT JOIN usuarios u ON u.id = c.usuario_id ORDER BY c.id")
    assert filas == [(1, "ana@correo.com"), (2, None), (3, "luis@correo.com")]


def test_los_materiales_json_pasan_a_detalle_de_cotizacion(migrada):
    filas = consultar(
        migrada,
        "SELECT d.cotizacion_id, e.nombre, d.cantidad FROM detalle_cotizacion d JOIN equipos e ON e.id = d.equipo_id ORDER BY 1, 2",
    )
    assert (1, "Monocristalino 550W", 5) in filas
    assert (2, "Panel Raro 450W", 6) in filas
    assert not any(nombre.lower() == "sin bateria" for _, nombre, _ in filas)


def test_cotizacion_sin_cliente_registrado_no_se_migra(migrada):
    assert consultar(migrada, "SELECT id FROM cotizaciones ORDER BY id") == [(1,), (2,)]


def test_sistema_instalado_conserva_potencia_fecha_y_origen(migrada):
    filas = consultar(migrada, "SELECT potencia_kwp, fecha_instalacion::text, cotizacion_id FROM sistemas_instalados ORDER BY id")
    assert [(float(p) if p else None, f, c) for p, f, c in filas] == [(2.75, "2026-11-15", 1), (None, None, None)]


def test_las_secuencias_continuan_despues_de_los_datos_migrados(migrada):
    with migrada.cursor() as cursor:
        cursor.execute("INSERT INTO calculos (consumo_mensual_kwh, paneles, cobertura_pct, ahorro_estimado_cop) VALUES (1, 1, 1, 1) RETURNING id")
        assert cursor.fetchone()[0] == 4
    migrada.rollback()
