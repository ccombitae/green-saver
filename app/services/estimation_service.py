"""
Dimensionamiento de un sistema solar fotovoltaico a partir de:
    - consumo mensual del hogar (kWh/mes)
    - Horas Solares Pico (HSP) de cada mes, predichas por el modelo de ML

Fórmula base (energía que produce UN panel en un mes):

    E_panel(mes) = P_panel(kW) × HSP(mes) × días(mes) × PR

    P_panel : potencia nominal del panel (por defecto 550 W = 0.55 kW)
    HSP     : horas solares pico del mes (kWh/m²/día) -> salida del modelo
    PR      : "performance ratio", pérdidas por temperatura, cableado,
              inversor, suciedad... (por defecto 0.80)

Paneles necesarios = techo( consumo mensual / energía promedio de un panel ).
Antes la app usaba un valor fijo de 75 kWh/panel/mes para todo el país; ahora
depende de la ciudad y del mes.
"""

from __future__ import annotations

import math

from app.ml.predictor import predecir_hsp_mensual
from app.services.costos_service import estimar_costos
from app.services.equipos_service import recomendar_baterias, recomendar_instalacion, recomendar_inversor

DIAS_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def energia_panel_mes(potencia_panel_w: float, hsp: float, dias: int, rendimiento: float) -> float:
    """kWh que produce un panel en un mes."""
    return (potencia_panel_w / 1000) * hsp * dias * rendimiento


def recomendacion(cobertura_anual: float, peor_mes: dict, fuente: str) -> str:
    if cobertura_anual >= 95:
        texto = "El sistema cubre prácticamente todo tu consumo durante el año."
    elif cobertura_anual >= 70:
        texto = "El sistema cubre la mayor parte de tu consumo; la red cubriría el resto."
    else:
        texto = "Cobertura parcial: considera más paneles o reducir el consumo."
    if peor_mes["cobertura_pct"] >= 100:
        texto += f" Incluso en {peor_mes['mes']}, el mes de menor producción, se cubre todo el consumo."
    else:
        texto += f" El mes de menor producción es {peor_mes['mes']} ({peor_mes['cobertura_pct']:.0f} % de cobertura)."
    if fuente != "modelo":
        texto += " Estimación aproximada: el modelo de predicción no estaba disponible."
    return texto


def estimar_sistema(
    consumo_mensual_kwh: float,
    ciudad_id: str | None,
    potencia_panel_w: float = 550,
    rendimiento: float = 0.80,
    tarifa_kwh_cop: float = 850,
    factor_emision_kg_kwh: float = 0.126,
) -> dict:
    if consumo_mensual_kwh <= 0:
        raise ValueError("El consumo mensual debe ser mayor que cero")

    prediccion = predecir_hsp_mensual(ciudad_id)
    hsp = prediccion["hsp_mensual"]

    energia_por_panel = [energia_panel_mes(potencia_panel_w, h, d, rendimiento) for h, d in zip(hsp, DIAS_MES)]
    energia_panel_promedio = sum(energia_por_panel) / 12
    paneles = max(1, math.ceil(consumo_mensual_kwh / energia_panel_promedio))

    detalle = []
    for i in range(12):
        generacion = paneles * energia_por_panel[i]
        autoconsumo = min(generacion, consumo_mensual_kwh)
        detalle.append(
            {
                "mes": MESES[i],
                "hsp": round(hsp[i], 2),
                "generacion_kwh": round(generacion, 1),
                "cobertura_pct": round(min(100.0, generacion / consumo_mensual_kwh * 100), 1),
                "ahorro_cop": round(autoconsumo * tarifa_kwh_cop),
            }
        )

    generacion_anual = sum(m["generacion_kwh"] for m in detalle)
    consumo_anual = consumo_mensual_kwh * 12
    autoconsumo_anual = sum(min(m["generacion_kwh"], consumo_mensual_kwh) for m in detalle)
    cobertura_anual = min(100.0, autoconsumo_anual / consumo_anual * 100)
    peor_mes = min(detalle, key=lambda m: m["generacion_kwh"])
    potencia_kwp = paneles * potencia_panel_w / 1000
    latitud = (prediccion["ciudad"] or {}).get("latitud")
    instalacion = recomendar_instalacion(paneles, potencia_panel_w, latitud)
    inversor = recomendar_inversor(potencia_kwp)
    baterias = recomendar_baterias(consumo_mensual_kwh)
    ahorro_anual = round(autoconsumo_anual * tarifa_kwh_cop)
    costos = estimar_costos(
        paneles,
        potencia_panel_w,
        potencia_kwp,
        inversor["potencia_kw"],
        baterias["respaldo_nocturno"]["modulos"],
        ahorro_anual,
    )

    return {
        "ciudad": prediccion["ciudad"],
        "fuente_hsp": prediccion["fuente"],
        "parametros": {
            "consumo_mensual_kwh": consumo_mensual_kwh,
            "potencia_panel_w": potencia_panel_w,
            "rendimiento": rendimiento,
            "tarifa_kwh_cop": tarifa_kwh_cop,
            "factor_emision_kg_kwh": factor_emision_kg_kwh,
        },
        "hsp_promedio": round(sum(hsp) / 12, 2),
        "paneles": paneles,
        "potencia_kwp": round(potencia_kwp, 2),
        "area_aprox_m2": instalacion["area_paneles_m2"],
        "generacion_anual_kwh": round(generacion_anual, 1),
        "generacion_mensual_promedio_kwh": round(generacion_anual / 12, 1),
        "rendimiento_especifico_kwh_kwp": round(generacion_anual / potencia_kwp),
        "cobertura_anual_pct": round(cobertura_anual, 1),
        "ahorro_anual_cop": ahorro_anual,
        "co2_evitado_kg_anual": round(autoconsumo_anual * factor_emision_kg_kwh, 1),
        "recomendacion": recomendacion(cobertura_anual, peor_mes, prediccion["fuente"]),
        "inversor": inversor,
        "baterias": baterias,
        "instalacion": instalacion,
        "costos": costos,
        "detalle_mensual": detalle,
        "hsp_historica": prediccion["hsp_historica"],
    }
