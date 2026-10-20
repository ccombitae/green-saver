"""
Paso 2 del pipeline: Análisis Exploratorio de Datos (EDA).

Responde preguntas sobre el recurso solar en Colombia ANTES de entrenar:
    - ¿Cuánta radiación (HSP) hay y cómo se distribuye?
    - ¿Qué ciudades tienen más y menos sol? ¿Dónde queda Girardot?
    - ¿Cómo cambia la radiación mes a mes (estacionalidad)?
    - ¿Qué variables climáticas se relacionan con la radiación?
    - ¿Hay datos faltantes o valores atípicos?

Genera:
    ml/reports/figuras/01..05_*.png        -> para el documento y la presentación
    ml/reports/eda_resumen.json            -> cifras clave del análisis
    app/ml/artifacts/eda_dashboard.json    -> datos agregados que la API sirve en
                                              GET /ml/eda para el dashboard

Uso (desde la raíz del repo):
    python ml/eda.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.ml.features import OBJETIVO, VARIABLES_CLIMA  # noqa: E402

DATOS_POR_DEFECTO = RAIZ / "ml" / "data" / "nasa_power_mensual.csv"
REPORTES_POR_DEFECTO = RAIZ / "ml" / "reports"
ARTEFACTOS_POR_DEFECTO = RAIZ / "app" / "ml" / "artifacts"

NOMBRES = {
    OBJETIVO: "HSP (kWh/m²/día)",
    "CLOUD_AMT": "Nubosidad (%)",
    "T2M": "Temperatura (°C)",
    "RH2M": "Humedad relativa (%)",
    "PRECTOTCORR": "Precipitación (mm/día)",
    "WS2M": "Viento (m/s)",
    "elevacion": "Elevación (m)",
    "latitud": "Latitud",
}
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
VERDE, OSCURO, GRIS, ROJO = "#00A859", "#1C1C1E", "#9CA3AF", "#ED3237"


def resumen(df: pd.DataFrame) -> dict:
    columnas = [OBJETIVO, *VARIABLES_CLIMA, "elevacion"]
    por_ciudad = df.groupby(["ciudad_id", "ciudad", "departamento"])[OBJETIVO].mean().sort_values(ascending=False)
    ranking = [
        {"ciudad_id": cid, "ciudad": c, "departamento": d, "hsp_promedio": round(float(v), 3)}
        for (cid, c, d), v in por_ciudad.items()
    ]
    perfil_mensual = df.groupby("mes")[OBJETIVO].mean()
    correlaciones = df[columnas].corr()[OBJETIVO].drop(OBJETIVO).sort_values()

    datos_girardot = df[df["ciudad_id"] == "girardot"]
    girardot = None
    if not datos_girardot.empty:
        pos = [r["ciudad_id"] for r in ranking].index("girardot") + 1
        girardot = {
            "hsp_promedio": round(float(datos_girardot[OBJETIVO].mean()), 3),
            "posicion_ranking": pos,
            "de": len(ranking),
            "mejor_mes": MESES[int(datos_girardot.groupby("mes")[OBJETIVO].mean().idxmax()) - 1],
            "peor_mes": MESES[int(datos_girardot.groupby("mes")[OBJETIVO].mean().idxmin()) - 1],
        }

    return {
        "filas": int(len(df)),
        "ciudades": int(df["ciudad_id"].nunique()),
        "periodo": f"{int(df['anio'].min())}-{int(df['anio'].max())}",
        "faltantes_por_variable": {c: int(df[c].isna().sum()) for c in columnas},
        "estadisticas_hsp": {
            k: round(float(v), 3) for k, v in df[OBJETIVO].describe().items() if k != "count"
        },
        "ranking_ciudades": ranking,
        "perfil_mensual_nacional": {MESES[int(m) - 1]: round(float(v), 3) for m, v in perfil_mensual.items()},
        "correlacion_con_hsp": {NOMBRES.get(k, k): round(float(v), 3) for k, v in correlaciones.items()},
        "girardot": girardot,
    }


def datos_dashboard(df: pd.DataFrame, res: dict) -> dict:
    """Agregados livianos que el frontend puede graficar sin procesar nada."""
    perfil_por_ciudad = (
        df.groupby(["ciudad_id", "mes"])[OBJETIVO].mean().round(3).unstack("mes").reindex(columns=range(1, 13))
    )
    tendencia_anual = df.groupby("anio")[OBJETIVO].mean().round(3)
    dispersion = (
        df.groupby(["ciudad_id", "ciudad"])[[OBJETIVO, "CLOUD_AMT", "PRECTOTCORR", "elevacion"]].mean().round(2).reset_index()
    )
    return {
        "meses": MESES,
        "resumen": {k: res[k] for k in ("filas", "ciudades", "periodo", "estadisticas_hsp", "girardot")},
        "ranking_ciudades": res["ranking_ciudades"],
        "perfil_mensual_nacional": list(res["perfil_mensual_nacional"].values()),
        "perfil_mensual_por_ciudad": {cid: [None if pd.isna(v) else float(v) for v in fila] for cid, fila in perfil_por_ciudad.iterrows()},
        "tendencia_anual": {"anios": [int(a) for a in tendencia_anual.index], "hsp": tendencia_anual.tolist()},
        "nubosidad_vs_hsp": dispersion.rename(columns={OBJETIVO: "hsp"}).to_dict(orient="records"),
        "correlacion_con_hsp": res["correlacion_con_hsp"],
    }


def graficar(df: pd.DataFrame, res: dict, carpeta: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    carpeta.mkdir(parents=True, exist_ok=True)

    # 01. Distribución de HSP
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(df[OBJETIVO], bins=40, color=VERDE, alpha=0.85)
    ax.axvline(df[OBJETIVO].mean(), color=OSCURO, linestyle="--", label=f"Promedio {df[OBJETIVO].mean():.2f}")
    ax.set_xlabel("HSP (kWh/m²/día)")
    ax.set_ylabel("Cantidad de meses")
    ax.set_title("Distribución de las Horas Solares Pico mensuales")
    ax.legend()
    fig.tight_layout()
    fig.savefig(carpeta / "01_distribucion_hsp.png", dpi=150)
    plt.close(fig)

    # 02. Ranking de ciudades (Girardot resaltada)
    ranking = pd.DataFrame(res["ranking_ciudades"]).iloc[::-1]
    colores = [ROJO if cid == "girardot" else VERDE for cid in ranking["ciudad_id"]]
    fig, ax = plt.subplots(figsize=(7, max(6, len(ranking) * 0.22)))
    ax.barh(ranking["ciudad"], ranking["hsp_promedio"], color=colores)
    ax.set_xlabel("HSP promedio (kWh/m²/día)")
    ax.set_title("Recurso solar promedio por ciudad (Girardot en rojo)")
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    fig.savefig(carpeta / "02_ranking_ciudades.png", dpi=150)
    plt.close(fig)

    # 03. Estacionalidad: boxplot por mes + Girardot y Bogotá
    fig, ax = plt.subplots(figsize=(8, 4.5))
    datos_mes = [df.loc[df["mes"] == m, OBJETIVO] for m in range(1, 13)]
    ax.boxplot(datos_mes, tick_labels=MESES, patch_artist=True,
               boxprops={"facecolor": "#D1F2E0", "color": GRIS}, medianprops={"color": OSCURO})
    # Se compara Girardot con la ciudad de más sol y una de las de menos sol.
    # (Bogotá no se usa: comparte celda de 1°x1° con Girardot y su línea quedaría encima)
    for cid, color, etiqueta in (("girardot", ROJO, "Girardot"), ("riohacha", "#F59E0B", "Riohacha"), ("quibdo", "#2563EB", "Quibdó")):
        sub = df[df["ciudad_id"] == cid]
        if not sub.empty:
            ax.plot(range(1, 13), sub.groupby("mes")[OBJETIVO].mean().reindex(range(1, 13)), marker="o", color=color, label=etiqueta)
    ax.set_ylabel("HSP (kWh/m²/día)")
    ax.set_title("Estacionalidad: radiación por mes en todas las ciudades")
    ax.legend()
    fig.tight_layout()
    fig.savefig(carpeta / "03_estacionalidad.png", dpi=150)
    plt.close(fig)

    # 04. Matriz de correlación
    columnas = [OBJETIVO, *VARIABLES_CLIMA, "elevacion", "latitud"]
    corr = df[columnas].corr()
    fig, ax = plt.subplots(figsize=(7, 6))
    imagen = ax.imshow(corr, cmap="RdYlGn", vmin=-1, vmax=1)
    etiquetas = [NOMBRES.get(c, c) for c in columnas]
    ax.set_xticks(range(len(columnas)), etiquetas, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(columnas)), etiquetas, fontsize=8)
    for i in range(len(columnas)):
        for j in range(len(columnas)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(imagen, ax=ax, shrink=0.8)
    ax.set_title("Correlación entre variables")
    fig.tight_layout()
    fig.savefig(carpeta / "04_correlaciones.png", dpi=150)
    plt.close(fig)

    # 05. Nubosidad vs HSP
    fig, ax = plt.subplots(figsize=(7, 4.5))
    puntos = ax.scatter(df["CLOUD_AMT"], df[OBJETIVO], c=df["elevacion"], cmap="viridis", s=6, alpha=0.5)
    fig.colorbar(puntos, ax=ax, label="Elevación (m)")
    ax.set_xlabel("Nubosidad (%)")
    ax.set_ylabel("HSP (kWh/m²/día)")
    ax.set_title("A más nubosidad, menos radiación")
    fig.tight_layout()
    fig.savefig(carpeta / "05_nubosidad_vs_hsp.png", dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Análisis exploratorio del recurso solar")
    parser.add_argument("--datos", type=Path, default=DATOS_POR_DEFECTO)
    parser.add_argument("--reportes", type=Path, default=REPORTES_POR_DEFECTO)
    parser.add_argument("--artefactos", type=Path, default=ARTEFACTOS_POR_DEFECTO)
    parser.add_argument("--sin-figuras", action="store_true")
    args = parser.parse_args()

    if not args.datos.exists():
        print(f"No existe {args.datos}. Ejecuta primero: python ml/descargar_datos.py")
        return 1

    df = pd.read_csv(args.datos)
    res = resumen(df)

    args.reportes.mkdir(parents=True, exist_ok=True)
    args.artefactos.mkdir(parents=True, exist_ok=True)
    (args.reportes / "eda_resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.artefactos / "eda_dashboard.json").write_text(
        json.dumps(datos_dashboard(df, res), ensure_ascii=False), encoding="utf-8"
    )
    if not args.sin_figuras:
        graficar(df, res, args.reportes / "figuras")

    print(f"Filas: {res['filas']} | Ciudades: {res['ciudades']} | Periodo: {res['periodo']}")
    print(f"HSP promedio nacional: {res['estadisticas_hsp']['mean']:.2f} kWh/m²/día")
    print("Top 3 ciudades:", ", ".join(f"{r['ciudad']} ({r['hsp_promedio']:.2f})" for r in res["ranking_ciudades"][:3]))
    if res["girardot"]:
        g = res["girardot"]
        print(f"Girardot: {g['hsp_promedio']:.2f} HSP, puesto {g['posicion_ranking']} de {g['de']}")
    print("Correlación con HSP:", res["correlacion_con_hsp"])
    print(f"Reportes en {args.reportes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
