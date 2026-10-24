"""
Recomendación de equipos e instalación a partir del sistema dimensionado.

Son valores de PREDIMENSIONAMIENTO para orientar al usuario y al equipo comercial;
el diseño definitivo (cadenas de paneles, calibre de cables, protecciones y puesta a
tierra según el RETIE) lo hace el instalador en la visita técnica.

Supuestos (todos configurables en este módulo):
- Panel monocristalino de 550 W: 2,28 m × 1,13 m (≈ 2,58 m²) y ≈ 27,5 kg. Para otras
  potencias se escala el área y el peso de forma proporcional.
- Inversor de conexión a red con relación DC/AC de hasta 1,25 (paneles hasta 25 % por
  encima de la potencia del inversor), práctica habitual en sistemas residenciales.
- Baterías de litio LiFePO4 en módulos de 5,12 kWh (48 V, 100 Ah), profundidad de
  descarga 90 % y eficiencia de carga y descarga 95 %.
- Alrededor de 40 % del consumo de un hogar ocurre cuando no hay sol (tarde y noche).
- Inclinación ≈ latitud, con mínimo de 10° para que la lluvia limpie los paneles, y
  orientación hacia el ecuador (en Colombia, hacia el sur).
"""

from __future__ import annotations

import math

AREA_PANEL_550_M2 = 2.28 * 1.13
PESO_PANEL_550_KG = 27.5
PESO_ESTRUCTURA_POR_PANEL_KG = 4.0
FACTOR_AREA_TECHO = 1.25  # pasillos de mantenimiento, bordes y separación de sombras

INVERSORES_COMERCIALES_KW = [1.5, 2, 3, 3.6, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50]
RELACION_DC_AC_MAX = 1.25

BATERIA_MODULO_KWH = 5.12
BATERIA_DOD = 0.90
BATERIA_EFICIENCIA = 0.95
FRACCION_CONSUMO_SIN_SOL = 0.40
INCLINACION_MINIMA = 10


def recomendar_inversor(potencia_kwp: float) -> dict:
    """Inversor comercial más pequeño que respeta la relación DC/AC máxima."""
    minimo_kw = potencia_kwp / RELACION_DC_AC_MAX
    potencia_kw = next((p for p in INVERSORES_COMERCIALES_KW if p >= minimo_kw), math.ceil(minimo_kw))
    conexion = "Monofásico o bifásico (según la acometida de la vivienda)" if potencia_kw <= 10 else "Trifásico"
    return {
        "tipo": "Inversor de conexión a red (on-grid)",
        "alternativa": "Inversor híbrido si se quieren baterías de respaldo",
        "potencia_kw": potencia_kw,
        "relacion_dc_ac": round(potencia_kwp / potencia_kw, 2),
        "conexion": conexion,
    }


def recomendar_baterias(consumo_mensual_kwh: float) -> dict:
    """Banco de baterías para dos escenarios: respaldo nocturno (híbrido) y un día de autonomía (aislado)."""
    consumo_diario = consumo_mensual_kwh / 30
    factor = BATERIA_DOD * BATERIA_EFICIENCIA

    def banco(energia_kwh: float) -> dict:
        capacidad = energia_kwh / factor
        modulos = max(1, math.ceil(capacidad / BATERIA_MODULO_KWH))
        return {
            "energia_necesaria_kwh": round(energia_kwh, 1),
            "capacidad_kwh": round(capacidad, 1),
            "modulos": modulos,
            "capacidad_instalada_kwh": round(modulos * BATERIA_MODULO_KWH, 2),
        }

    return {
        "opcional": True,
        "tecnologia": "Litio LiFePO4, módulos de " + f"{BATERIA_MODULO_KWH:.2f}".replace(".", ",") + " kWh a 48 V",
        "respaldo_nocturno": banco(consumo_diario * FRACCION_CONSUMO_SIN_SOL),
        "autonomia_un_dia": banco(consumo_diario),
        "nota": "Un sistema conectado a la red no necesita baterías: la red suple la energía de la noche. "
        "Las baterías sirven como respaldo ante cortes o para un sistema aislado.",
    }


def recomendar_instalacion(paneles: int, potencia_panel_w: float, latitud: float | None) -> dict:
    escala = potencia_panel_w / 550
    area_paneles = paneles * AREA_PANEL_550_M2 * escala
    peso = paneles * (PESO_PANEL_550_KG * escala + PESO_ESTRUCTURA_POR_PANEL_KG)
    if latitud is None:
        inclinacion = INCLINACION_MINIMA
        orientacion = "Hacia el ecuador (en Colombia, hacia el sur)"
    else:
        inclinacion = max(INCLINACION_MINIMA, round(abs(latitud)))
        orientacion = "Hacia el sur" if latitud >= 0 else "Hacia el norte"
    return {
        "area_paneles_m2": round(area_paneles, 1),
        "area_techo_recomendada_m2": round(area_paneles * FACTOR_AREA_TECHO, 1),
        "peso_total_kg": round(peso),
        "carga_kg_m2": round(peso / area_paneles, 1),
        "inclinacion_grados": inclinacion,
        "orientacion": orientacion,
        "notas": [
            "Techo sin sombras de árboles, tanques o edificios entre las 9:00 y las 15:00.",
            "Verificar que la estructura del techo soporte la carga indicada.",
            "Conexión a la red como autogenerador a pequeña escala (Resolución CREG 174 de 2021): "
            "el trámite se hace ante el operador de red.",
            "El instalador define cableado, protecciones y puesta a tierra según el RETIE.",
        ],
    }
