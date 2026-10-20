"""Pruebas unitarias de la conversión de datos de NASA POWER."""

from ml.descargar_datos import json_a_filas
from tests.datos_sinteticos import CIUDADES_PRUEBA, respuesta_falsa_nasa

CIUDAD = CIUDADES_PRUEBA[0]


def test_descarta_el_promedio_anual_mes_13():
    filas = json_a_filas(CIUDAD, respuesta_falsa_nasa(CIUDAD, 2020, 2021))
    assert len(filas) == 24
    assert {f["mes"] for f in filas} == set(range(1, 13))


def test_toma_la_elevacion_de_la_geometria():
    filas = json_a_filas(CIUDAD, respuesta_falsa_nasa(CIUDAD, 2020, 2020))
    assert all(f["elevacion"] == CIUDAD["elev"] for f in filas)


def test_convierte_valor_faltante_en_none():
    datos = respuesta_falsa_nasa(CIUDAD, 2020, 2020)
    datos["properties"]["parameter"]["T2M"]["202003"] = -999.0
    filas = json_a_filas(CIUDAD, datos)
    marzo = next(f for f in filas if f["mes"] == 3)
    assert marzo["T2M"] is None
    assert marzo["ALLSKY_SFC_SW_DWN"] is not None
