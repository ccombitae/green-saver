"""
Datos SINTÉTICOS, solo para las pruebas automáticas.

Imitan el formato de respuesta de NASA POWER para poder probar el pipeline
(descarga -> EDA -> entrenamiento -> API) sin internet y en segundos.
NO se usan para entrenar el modelo real ni para reportar métricas.
"""

from __future__ import annotations

import csv
import math
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ml.descargar_datos import PARAMETROS, json_a_filas  # noqa: E402

CIUDADES_PRUEBA = [
    {"id": "girardot", "nombre": "Girardot", "departamento": "Cundinamarca", "latitud": "4.30", "longitud": "-74.80", "elev": 400},
    {"id": "bogota", "nombre": "Bogotá D.C.", "departamento": "Bogotá D.C.", "latitud": "4.71", "longitud": "-74.07", "elev": 2600},
    {"id": "riohacha", "nombre": "Riohacha", "departamento": "La Guajira", "latitud": "11.54", "longitud": "-72.91", "elev": 20},
    {"id": "quibdo", "nombre": "Quibdó", "departamento": "Chocó", "latitud": "5.69", "longitud": "-76.66", "elev": 50},
    {"id": "neiva", "nombre": "Neiva", "departamento": "Huila", "latitud": "2.93", "longitud": "-75.28", "elev": 450},
    {"id": "cucuta", "nombre": "Cúcuta", "departamento": "Norte de Santander", "latitud": "7.89", "longitud": "-72.51", "elev": 320},
    {"id": "pasto", "nombre": "Pasto", "departamento": "Nariño", "latitud": "1.21", "longitud": "-77.28", "elev": 2500},
    {"id": "leticia", "nombre": "Leticia", "departamento": "Amazonas", "latitud": "-4.21", "longitud": "-69.94", "elev": 90},
]


def respuesta_falsa_nasa(ciudad: dict, inicio: int = 2018, fin: int = 2022, semilla: int = 0) -> dict:
    """Genera un JSON con la misma estructura que devuelve NASA POWER."""
    rnd = random.Random(f"{ciudad['id']}-{semilla}")
    base_nubes = 45 + (30 if ciudad["id"] in {"quibdo", "leticia"} else 0) - (20 if ciudad["id"] == "riohacha" else 0)
    parametros = {p: {} for p in PARAMETROS}
    for anio in range(inicio, fin + 1):
        for mes in range(1, 14):
            clave = f"{anio}{mes:02d}"
            nubes = max(5.0, min(95.0, base_nubes + 12 * math.cos(2 * math.pi * mes / 12) + rnd.gauss(0, 4)))
            hsp = 7.2 - 0.045 * nubes + 0.0002 * ciudad["elev"] + rnd.gauss(0, 0.15)
            parametros["ALLSKY_SFC_SW_DWN"][clave] = round(hsp, 2)
            parametros["CLOUD_AMT"][clave] = round(nubes, 2)
            parametros["T2M"][clave] = round(28 - 0.0055 * ciudad["elev"] + rnd.gauss(0, 0.5), 2)
            parametros["RH2M"][clave] = round(60 + nubes * 0.3 + rnd.gauss(0, 2), 2)
            parametros["PRECTOTCORR"][clave] = round(max(0.0, nubes / 10 + rnd.gauss(0, 1)), 2)
            parametros["WS2M"][clave] = round(abs(2 + rnd.gauss(0, 0.5)), 2)
    return {
        "geometry": {"coordinates": [float(ciudad["longitud"]), float(ciudad["latitud"]), ciudad["elev"]]},
        "properties": {"parameter": parametros},
    }


def escribir_csv_sintetico(ruta: Path) -> Path:
    filas = []
    for ciudad in CIUDADES_PRUEBA:
        filas.extend(json_a_filas(ciudad, respuesta_falsa_nasa(ciudad)))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)
    return ruta
