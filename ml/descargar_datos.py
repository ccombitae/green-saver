"""
Paso 1 del pipeline de Machine Learning de Green Saver: descarga de datos.

Descarga datos climáticos MENSUALES de la API pública NASA POWER
(https://power.larc.nasa.gov) para cada ciudad de `ml/ciudades.csv` y los guarda
en un único CSV "largo" (una fila por ciudad y mes):

    ml/data/nasa_power_mensual.csv

Variables descargadas (comunidad "RE" = Renewable Energy):
    ALLSKY_SFC_SW_DWN  Irradiación solar global en superficie (kWh/m²/día).
                       Numéricamente equivale a las Horas Solares Pico (HSP):
                       es la VARIABLE OBJETIVO del modelo.
    CLOUD_AMT          Nubosidad promedio (%)
    T2M                Temperatura a 2 m (°C)
    RH2M               Humedad relativa a 2 m (%)
    PRECTOTCORR        Precipitación (mm/día)
    WS2M               Velocidad del viento a 2 m (m/s)

No requiere API key. Uso (desde la raíz del repo):

    pip install -r requirements-dev.txt
    python ml/descargar_datos.py                # 2005-2024, todas las ciudades
    python ml/descargar_datos.py --inicio 2015  # periodo más corto
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CIUDADES_CSV = BASE_DIR / "ciudades.csv"
SALIDA_CSV = BASE_DIR / "data" / "nasa_power_mensual.csv"

API_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
PARAMETROS = ["ALLSKY_SFC_SW_DWN", "CLOUD_AMT", "T2M", "RH2M", "PRECTOTCORR", "WS2M"]
VALOR_FALTANTE = -999.0  # NASA POWER marca así los datos faltantes


def leer_ciudades() -> list[dict]:
    with CIUDADES_CSV.open(encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def descargar_ciudad(ciudad: dict, inicio: int, fin: int, reintentos: int = 3) -> dict:
    """Consulta NASA POWER para una ciudad y devuelve el JSON de respuesta."""
    params = {
        "parameters": ",".join(PARAMETROS),
        "community": "RE",
        "latitude": ciudad["latitud"],
        "longitude": ciudad["longitud"],
        "start": inicio,
        "end": fin,
        "format": "JSON",
    }
    for intento in range(1, reintentos + 1):
        try:
            respuesta = requests.get(API_URL, params=params, timeout=90)
            respuesta.raise_for_status()
            return respuesta.json()
        except requests.RequestException as exc:
            if intento == reintentos:
                raise
            espera = 5 * intento
            print(f"   ! error ({exc}); reintento {intento}/{reintentos} en {espera}s")
            time.sleep(espera)
    raise RuntimeError("inalcanzable")


def json_a_filas(ciudad: dict, datos: dict) -> list[dict]:
    """
    Convierte la respuesta de NASA POWER en filas (ciudad, año, mes, variables...).

    Las claves de NASA vienen como 'YYYYMM'; el mes '13' es el promedio anual
    y se descarta porque no es un mes real.
    """
    parametros = datos["properties"]["parameter"]
    # geometry.coordinates = [longitud, latitud, elevación de la celda (m)]
    coordenadas = datos.get("geometry", {}).get("coordinates", [None, None, None])
    elevacion = coordenadas[2] if len(coordenadas) > 2 else None

    filas = []
    for clave in sorted(parametros[PARAMETROS[0]].keys()):
        anio, mes = int(clave[:4]), int(clave[4:])
        if mes == 13:
            continue
        fila = {
            "ciudad_id": ciudad["id"],
            "ciudad": ciudad["nombre"],
            "departamento": ciudad["departamento"],
            "latitud": float(ciudad["latitud"]),
            "longitud": float(ciudad["longitud"]),
            "elevacion": elevacion,
            "anio": anio,
            "mes": mes,
        }
        for parametro in PARAMETROS:
            valor = parametros.get(parametro, {}).get(clave)
            fila[parametro] = None if valor is None or valor == VALOR_FALTANTE else valor
        filas.append(fila)
    return filas


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga datos NASA POWER para Green Saver")
    parser.add_argument("--inicio", type=int, default=2005, help="Año inicial (por defecto 2005)")
    parser.add_argument("--fin", type=int, default=2024, help="Año final (por defecto 2024)")
    args = parser.parse_args()

    ciudades = leer_ciudades()
    SALIDA_CSV.parent.mkdir(parents=True, exist_ok=True)

    todas_las_filas: list[dict] = []
    fallidas: list[str] = []
    for indice, ciudad in enumerate(ciudades, start=1):
        print(f"[{indice:02d}/{len(ciudades)}] {ciudad['nombre']} ({ciudad['departamento']})")
        try:
            datos = descargar_ciudad(ciudad, args.inicio, args.fin)
            todas_las_filas.extend(json_a_filas(ciudad, datos))
        except Exception as exc:  # noqa: BLE001 - se reporta y se continúa con la siguiente ciudad
            print(f"   x no se pudo descargar: {exc}")
            fallidas.append(ciudad["nombre"])
        time.sleep(1)  # pausa corta para no saturar la API pública

    if not todas_las_filas:
        print("No se descargó ningún dato. Revisa tu conexión a internet.")
        return 1

    columnas = list(todas_las_filas[0].keys())
    with SALIDA_CSV.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(todas_las_filas)

    print(f"\nListo: {len(todas_las_filas)} filas guardadas en {SALIDA_CSV}")
    if fallidas:
        print(f"Ciudades sin datos ({len(fallidas)}): {', '.join(fallidas)}. Vuelve a ejecutar el script.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
