"""
Carga los artefactos del modelo entrenado y predice las Horas Solares Pico (HSP)
de cada mes para una ciudad.

Artefactos (generados por ml/entrenar.py y ml/eda.py):
    app/ml/artifacts/modelo_hsp.joblib   modelo de scikit-learn
    app/ml/artifacts/climatologia.csv    clima típico de cada ciudad por mes
    app/ml/artifacts/metadata.json       nombre del modelo, métricas, fecha
    app/ml/artifacts/eda_dashboard.json  datos agregados para el dashboard

Estrategia de respaldo (la API nunca se cae por falta del modelo):
    1. "modelo"    -> hay modelo + climatología: se predice con ML.
    2. "historico" -> no hay modelo pero sí climatología: se usa el promedio
                      histórico observado de la ciudad.
    3. "respaldo"  -> no hay artefactos: se usa un valor nacional fijo.
"""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path

from app.ml.features import construir_vector

CARPETA_ARTEFACTOS = Path(__file__).resolve().parent / "artifacts"
HSP_RESPALDO = 4.5  # kWh/m²/día, valor de referencia conservador para Colombia


class CiudadNoEncontrada(LookupError):
    pass


@lru_cache(maxsize=1)
def _climatologia() -> dict[str, dict]:
    """{ciudad_id: {"nombre", "departamento", "meses": {1: fila, ..., 12: fila}}}"""
    ruta = CARPETA_ARTEFACTOS / "climatologia.csv"
    if not ruta.exists():
        return {}
    ciudades: dict[str, dict] = {}
    with ruta.open(encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            ciudad = ciudades.setdefault(
                fila["ciudad_id"],
                {"nombre": fila["ciudad"], "departamento": fila["departamento"], "meses": {}},
            )
            ciudad["meses"][int(fila["mes"])] = fila
    return ciudades


@lru_cache(maxsize=1)
def _modelo():
    ruta = CARPETA_ARTEFACTOS / "modelo_hsp.joblib"
    if not ruta.exists():
        return None
    import joblib  # import diferido: la API arranca aunque no se use el modelo

    return joblib.load(ruta)


@lru_cache(maxsize=1)
def metadata() -> dict:
    ruta = CARPETA_ARTEFACTOS / "metadata.json"
    if not ruta.exists():
        return {"modelo": None, "estado": "sin entrenar"}
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["estado"] = "entrenado"
    return datos


@lru_cache(maxsize=1)
def datos_eda() -> dict | None:
    ruta = CARPETA_ARTEFACTOS / "eda_dashboard.json"
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def recargar() -> None:
    """Limpia la caché (útil en pruebas o tras reentrenar sin reiniciar)."""
    for funcion in (_climatologia, _modelo, metadata, datos_eda):
        funcion.cache_clear()


def listar_ciudades() -> list[dict]:
    return sorted(
        (
            {"id": cid, "nombre": c["nombre"], "departamento": c["departamento"]}
            for cid, c in _climatologia().items()
        ),
        key=lambda c: (c["id"] != "girardot", c["nombre"]),  # Girardot primero
    )


def predecir_hsp_mensual(ciudad_id: str | None) -> dict:
    """
    Devuelve {"fuente", "ciudad", "hsp_mensual": [12 valores], "hsp_historica": [12 valores|None]}.
    """
    clima = _climatologia()
    if not clima:
        return {
            "fuente": "respaldo",
            "ciudad": None,
            "hsp_mensual": [HSP_RESPALDO] * 12,
            "hsp_historica": [None] * 12,
        }

    if not ciudad_id or ciudad_id not in clima:
        raise CiudadNoEncontrada(f"Ciudad '{ciudad_id}' no está en el catálogo")

    ciudad = clima[ciudad_id]
    filas = [ciudad["meses"][mes] for mes in range(1, 13)]
    historica = [round(float(f["hsp_historica"]), 3) for f in filas]

    modelo = _modelo()
    if modelo is None:
        return {
            "fuente": "historico",
            "ciudad": {"id": ciudad_id, "nombre": ciudad["nombre"], "departamento": ciudad["departamento"]},
            "hsp_mensual": historica,
            "hsp_historica": historica,
        }

    matriz = [construir_vector(fila) for fila in filas]
    predicciones = [round(max(0.5, float(valor)), 3) for valor in modelo.predict(matriz)]
    return {
        "fuente": "modelo",
        "ciudad": {"id": ciudad_id, "nombre": ciudad["nombre"], "departamento": ciudad["departamento"]},
        "hsp_mensual": predicciones,
        "hsp_historica": historica,
    }
