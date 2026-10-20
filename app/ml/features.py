"""
Definición ÚNICA de las variables de entrada (features) del modelo.

Se usa tanto en el entrenamiento (ml/entrenar.py) como en la predicción dentro
de la API (app/ml/predictor.py). Mantenerla en un solo lugar evita que el
modelo reciba las columnas en un orden distinto al que aprendió.
"""

from __future__ import annotations

import math

# Variables climáticas que vienen de NASA POWER (ver ml/descargar_datos.py)
VARIABLES_CLIMA = ["CLOUD_AMT", "T2M", "RH2M", "PRECTOTCORR", "WS2M"]

# Orden exacto de las columnas que recibe el modelo
FEATURES = ["latitud", "longitud", "elevacion", "mes_sin", "mes_cos", *VARIABLES_CLIMA]

# Variable objetivo: irradiación global diaria (kWh/m²/día) = Horas Solares Pico
OBJETIVO = "ALLSKY_SFC_SW_DWN"


def codificar_mes(mes: int) -> tuple[float, float]:
    """
    Codificación cíclica del mes: diciembre (12) y enero (1) quedan "cerca".
    Si se usara el número del mes tal cual, el modelo creería que 12 y 1
    están muy lejos.
    """
    angulo = 2 * math.pi * (mes - 1) / 12
    return math.sin(angulo), math.cos(angulo)


def construir_vector(fila: dict) -> list[float]:
    """Convierte un diccionario con los datos de una ciudad-mes en la lista de features."""
    mes_sin, mes_cos = codificar_mes(int(fila["mes"]))
    valores = {
        "latitud": float(fila["latitud"]),
        "longitud": float(fila["longitud"]),
        "elevacion": float(fila["elevacion"]),
        "mes_sin": mes_sin,
        "mes_cos": mes_cos,
    }
    for variable in VARIABLES_CLIMA:
        valores[variable] = float(fila[variable])
    return [valores[nombre] for nombre in FEATURES]
