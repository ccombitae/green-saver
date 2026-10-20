"""
Paso 3 del pipeline: entrenamiento y evaluación del modelo de Machine Learning.

Problema: REGRESIÓN SUPERVISADA.
    Entrada  -> ubicación (latitud, longitud, elevación), mes y clima del mes
                (nubosidad, temperatura, humedad, lluvia, viento).
    Salida   -> Horas Solares Pico (HSP) = irradiación global diaria en kWh/m²/día.

Con las HSP que predice el modelo, la API calcula cuánta energía produce un panel
en la ciudad del usuario, en vez de usar el valor fijo de 75 kWh/panel/mes que
tenía la calculadora anterior.

Metodología de validación:
    Se usa validación cruzada AGRUPADA (GroupKFold) por celda geográfica de 1°x1°
    (la resolución de los datos solares de NASA). Así el modelo siempre se evalúa
    con zonas que NO vio en el entrenamiento, que es justo el caso real: estimar
    la radiación de un municipio nuevo. Si se mezclaran filas de la misma zona en
    entrenamiento y prueba, las métricas saldrían infladas (fuga de datos).

Modelos comparados:
    1. Línea base: promedio nacional del mes (sin ML), para saber si el ML aporta.
    2. Regresión lineal (con estandarización).
    3. Random Forest.
    4. Gradient Boosting (HistGradientBoostingRegressor).

Se elige el de menor MAE, se reentrena con todos los datos y se guardan los
artefactos que usa la API en app/ml/artifacts/.

Uso (desde la raíz del repo, después de descargar los datos):
    python ml/entrenar.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.ml.features import FEATURES, OBJETIVO, VARIABLES_CLIMA, codificar_mes  # noqa: E402

DATOS_POR_DEFECTO = RAIZ / "ml" / "data" / "nasa_power_mensual.csv"
ARTEFACTOS_POR_DEFECTO = RAIZ / "app" / "ml" / "artifacts"
REPORTES_POR_DEFECTO = RAIZ / "ml" / "reports"
SEMILLA = 42


# ---------------------------------------------------------------------------
# Preparación de datos
# ---------------------------------------------------------------------------
def cargar_datos(ruta: Path) -> pd.DataFrame:
    df = pd.read_csv(ruta)
    filas_iniciales = len(df)
    df = df.dropna(subset=[OBJETIVO, "elevacion", *VARIABLES_CLIMA])
    print(f"Datos: {len(df)} filas útiles de {filas_iniciales} ({df['ciudad_id'].nunique()} ciudades)")

    seno_coseno = df["mes"].apply(lambda m: pd.Series(codificar_mes(int(m)), index=["mes_sin", "mes_cos"]))
    df = pd.concat([df, seno_coseno], axis=1)
    # Celda de 1°x1°: ciudades en la misma celda comparten el dato solar de NASA
    df["celda"] = np.floor(df["latitud"]).astype(int).astype(str) + "_" + np.floor(df["longitud"]).astype(int).astype(str)
    return df


def crear_modelos() -> dict:
    return {
        "Regresión lineal": make_pipeline(StandardScaler(), LinearRegression()),
        "Random Forest": RandomForestRegressor(
            n_estimators=200, min_samples_leaf=3, max_features=0.7, n_jobs=-1, random_state=SEMILLA
        ),
        "Gradient Boosting": HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.05, min_samples_leaf=20, random_state=SEMILLA
        ),
    }


def metricas(y_real: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "mae": float(mean_absolute_error(y_real, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_real, y_pred))),
        "r2": float(r2_score(y_real, y_pred)),
        "mape_pct": float(np.mean(np.abs((y_real - y_pred) / y_real)) * 100),
    }


# ---------------------------------------------------------------------------
# Evaluación
# ---------------------------------------------------------------------------
def evaluar(df: pd.DataFrame) -> tuple[dict, dict]:
    """Validación cruzada agrupada. Devuelve métricas y predicciones fuera de muestra."""
    X = df[FEATURES].to_numpy(dtype=float)
    y = df[OBJETIVO].to_numpy(dtype=float)
    grupos = df["celda"].to_numpy()
    n_splits = min(5, len(np.unique(grupos)))
    cv = GroupKFold(n_splits=n_splits)

    resultados: dict[str, dict] = {}
    predicciones: dict[str, np.ndarray] = {}

    # Línea base: promedio del mes calculado SOLO con las zonas de entrenamiento
    pred_base = np.zeros_like(y)
    for idx_train, idx_test in cv.split(X, y, grupos):
        promedio_mes = df.iloc[idx_train].groupby("mes")[OBJETIVO].mean()
        pred_base[idx_test] = df.iloc[idx_test]["mes"].map(promedio_mes).to_numpy()
    resultados["Línea base (promedio del mes)"] = metricas(y, pred_base)
    predicciones["Línea base (promedio del mes)"] = pred_base

    for nombre, modelo in crear_modelos().items():
        pred = np.zeros_like(y)
        for idx_train, idx_test in cv.split(X, y, grupos):
            modelo.fit(X[idx_train], y[idx_train])
            pred[idx_test] = modelo.predict(X[idx_test])
        resultados[nombre] = metricas(y, pred)
        predicciones[nombre] = pred
        r = resultados[nombre]
        print(f"  {nombre:<20} MAE={r['mae']:.3f}  RMSE={r['rmse']:.3f}  R²={r['r2']:.3f}  MAPE={r['mape_pct']:.1f}%")

    r = resultados["Línea base (promedio del mes)"]
    print(f"  {'Línea base':<20} MAE={r['mae']:.3f}  RMSE={r['rmse']:.3f}  R²={r['r2']:.3f}  MAPE={r['mape_pct']:.1f}%")
    return resultados, predicciones


# ---------------------------------------------------------------------------
# Artefactos para la API
# ---------------------------------------------------------------------------
def construir_climatologia(df: pd.DataFrame) -> pd.DataFrame:
    """
    Promedio histórico por ciudad y mes. Es lo que la API le pasa al modelo:
    "el clima típico de enero en Girardot", "el de febrero", etc.
    También guarda la HSP observada para mostrarla junto a la predicción.
    """
    columnas = ["latitud", "longitud", "elevacion", *VARIABLES_CLIMA, OBJETIVO]
    clima = df.groupby(["ciudad_id", "ciudad", "departamento", "mes"], as_index=False)[columnas].mean()
    clima = clima.rename(columns={OBJETIVO: "hsp_historica"})
    return clima.round(4)


def guardar_figuras(df, y, predicciones, mejor, modelo_final, carpeta: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    carpeta.mkdir(parents=True, exist_ok=True)

    # 1. Observado vs predicho (validación cruzada)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(y, predicciones[mejor], s=6, alpha=0.35, color="#00A859")
    limites = [min(y.min(), predicciones[mejor].min()), max(y.max(), predicciones[mejor].max())]
    ax.plot(limites, limites, color="#1C1C1E", linewidth=1, linestyle="--", label="Predicción perfecta")
    ax.set_xlabel("HSP observada (kWh/m²/día)")
    ax.set_ylabel("HSP predicha (kWh/m²/día)")
    ax.set_title(f"{mejor}: observado vs predicho\n(validación cruzada por zonas)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(carpeta / "06_observado_vs_predicho.png", dpi=150)
    plt.close(fig)

    # 2. Distribución de errores
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(predicciones[mejor] - y, bins=50, color="#00A859", alpha=0.85)
    ax.axvline(0, color="#1C1C1E", linewidth=1)
    ax.set_xlabel("Error (predicho − observado), kWh/m²/día")
    ax.set_ylabel("Cantidad de meses")
    ax.set_title(f"Distribución del error — {mejor}")
    fig.tight_layout()
    fig.savefig(carpeta / "07_distribucion_errores.png", dpi=150)
    plt.close(fig)

    # 3. Importancia de variables (por permutación, sirve para cualquier modelo)
    X = df[FEATURES].to_numpy(dtype=float)
    importancia = permutation_importance(modelo_final, X, y, n_repeats=5, random_state=SEMILLA, n_jobs=-1)
    orden = np.argsort(importancia.importances_mean)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh(np.array(FEATURES)[orden], importancia.importances_mean[orden], color="#00A859")
    ax.set_xlabel("Pérdida de precisión al desordenar la variable")
    ax.set_title("Importancia de las variables")
    fig.tight_layout()
    fig.savefig(carpeta / "08_importancia_variables.png", dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Entrena el modelo de HSP de Green Saver")
    parser.add_argument("--datos", type=Path, default=DATOS_POR_DEFECTO)
    parser.add_argument("--artefactos", type=Path, default=ARTEFACTOS_POR_DEFECTO)
    parser.add_argument("--reportes", type=Path, default=REPORTES_POR_DEFECTO)
    parser.add_argument("--sin-figuras", action="store_true", help="No generar gráficas (más rápido)")
    args = parser.parse_args()

    if not args.datos.exists():
        print(f"No existe {args.datos}. Ejecuta primero: python ml/descargar_datos.py")
        return 1

    df = cargar_datos(args.datos)
    print("\nValidación cruzada agrupada por zona geográfica:")
    resultados, predicciones = evaluar(df)

    candidatos = {k: v for k, v in resultados.items() if not k.startswith("Línea base")}
    mejor = min(candidatos, key=lambda nombre: candidatos[nombre]["mae"])
    print(f"\nModelo elegido: {mejor} (menor MAE)")

    modelo_final = crear_modelos()[mejor]
    X = df[FEATURES].to_numpy(dtype=float)
    y = df[OBJETIVO].to_numpy(dtype=float)
    modelo_final.fit(X, y)

    args.artefactos.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo_final, args.artefactos / "modelo_hsp.joblib", compress=3)
    construir_climatologia(df).to_csv(args.artefactos / "climatologia.csv", index=False)

    metadata = {
        "modelo": mejor,
        "objetivo": "Horas Solares Pico (HSP) = irradiación global diaria, kWh/m²/día",
        "features": FEATURES,
        "fuente_datos": "NASA POWER (power.larc.nasa.gov), comunidad RE, datos mensuales",
        "periodo": f"{int(df['anio'].min())}-{int(df['anio'].max())}",
        "filas_entrenamiento": int(len(df)),
        "ciudades": int(df["ciudad_id"].nunique()),
        "zonas_1x1": int(df["celda"].nunique()),
        "validacion": "GroupKFold por celda geográfica de 1°x1°",
        "metricas_validacion": resultados,
        "fecha_entrenamiento": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version_sklearn": sklearn.__version__,
    }
    (args.artefactos / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.reportes).mkdir(parents=True, exist_ok=True)
    (args.reportes / "metricas_modelos.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if not args.sin_figuras:
        guardar_figuras(df, y, predicciones, mejor, modelo_final, args.reportes / "figuras")

    print(f"Artefactos guardados en {args.artefactos}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
