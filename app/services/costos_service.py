"""
Costo estimado del sistema e instalación (pesos colombianos).

No existe una API pública con precios en tiempo real de equipos solares en Colombia,
así que se usa una tabla de PRECIOS DE REFERENCIA consultados en tiendas y guías del
mercado colombiano en octubre de 2026 (ver FUENTES). Los precios cambian: la tabla se
actualiza aquí y se publica con un nuevo despliegue.

Método:
1. Equipos con precio de catálogo: paneles e inversor (y baterías si se piden).
2. Rubros sin precio unitario publicado (estructura, protecciones y cableado, mano de
   obra, trámites y certificación RETIE) se calculan con la participación típica de
   cada rubro en el costo total de un sistema residencial conectado a la red
   (OPS Colombia, 2026): estructura 10-15 %, mano de obra 15-20 %, protecciones y
   cableado 5-10 %, trámites 5-10 %. Se usa el punto medio de cada rango.
3. Se suma el medidor bidireccional (200.000 a 800.000 COP; Vexta Energy, 2026).
"""

from __future__ import annotations

import math

FECHA_PRECIOS = "octubre de 2026"

PRECIO_PANEL_550_COP = 580_000  # Autosolar (2026): modelos residenciales de 500-550 W "rondan los $580.000"
RANGO_PANEL_550_COP = (383_040, 962_900)  # Emergente (Trina 550 W) y Homecenter (JA Solar 550 W)

# Inversores de conexión a red (INELDEC, categoría On Grid, octubre de 2026): (kW, precio, modelo de referencia)
INVERSORES_ON_GRID = [
    (3.3, 1_300_000, "On Grid 3,3 kW bifásico"),
    (3.6, 2_260_000, "On Grid 3,6 kW bifásico"),
    (5.0, 1_900_000, "On Grid 5 kW bifásico"),
    (6.0, 2_670_000, "On Grid 6 kW bifásico"),
    (8.0, 2_750_000, "On Grid 8 kW"),
    (10.0, 3_050_000, "On Grid 10 kW bifásico"),
    (15.0, 4_750_000, "On Grid 15 kW trifásico"),
]
PRECIO_INVERSOR_HIBRIDO_5KW_COP = 7_990_000  # INELDEC: híbrido 5 kW 48 V
PRECIO_BATERIA_5_12_KWH_COP = 5_624_250  # Energía Solar Colombia: litio 51,2 V 100 Ah (5,12 kWh)
PRECIO_MEDIDOR_BIDIRECCIONAL_COP = 500_000  # punto medio de 200.000-800.000 (Vexta Energy, 2026)

# Participación en el costo total del sistema (punto medio de cada rango de OPS Colombia, 2026)
PARTICIPACION = {
    "estructura": 0.125,
    "mano_obra": 0.175,
    "protecciones": 0.075,
    "tramites": 0.075,
}
REFERENCIA_MERCADO_COP_KWP = (2_800_000, 5_000_000)  # Vexta Energy y OPS Colombia (2026)
MANTENIMIENTO_ANUAL_COP = (300_000, 800_000)  # Voltiva (2026)

FUENTES = [
    "Autosolar Colombia (2026). ¿Cuánto cuesta un panel solar en Colombia? Precios 2026.",
    "Emergente (2026). Panel solar de 550 W monocristalino TrinaSolar.",
    "Homecenter Colombia (2026). Panel JA Solar 550 W.",
    "INELDEC (2026). Inversores On Grid.",
    "Energía Solar Colombia (2026). Batería de litio 51,2 V 100 Ah MUST (5,12 kWh).",
    "OPS Colombia (2026). ¿Cuánto cuesta realmente un sistema solar en Colombia?",
    "Vexta Energy (2026). ¿Cuánto cuesta instalar paneles solares en Colombia en 2026?",
    "Voltiva (2026). Cuánto cuesta instalar paneles solares en Colombia.",
]


def precio_inversor(potencia_kw: float) -> tuple[float, int, str]:
    """Modelo de referencia más pequeño con potencia ≥ a la recomendada."""
    for kw, precio, modelo in INVERSORES_ON_GRID:
        if kw >= potencia_kw:
            return kw, precio, modelo
    # Sistemas más grandes que el catálogo: varios inversores de 15 kW
    kw, precio, modelo = INVERSORES_ON_GRID[-1]
    n = math.ceil(potencia_kw / kw)
    return kw * n, precio * n, f"{n} × {modelo}"


def estimar_costos(
    paneles: int,
    potencia_panel_w: float,
    potencia_kwp: float,
    inversor_kw: float,
    modulos_respaldo: int,
    ahorro_anual_cop: float,
) -> dict:
    precio_panel = round(PRECIO_PANEL_550_COP * potencia_panel_w / 550)
    costo_paneles = paneles * precio_panel
    kw_ref, costo_inversor, modelo_inversor = precio_inversor(inversor_kw)

    equipos = costo_paneles + costo_inversor
    total_sin_medidor = equipos / (1 - sum(PARTICIPACION.values()))
    rubros = {k: round(total_sin_medidor * v) for k, v in PARTICIPACION.items()}
    total = round(equipos + sum(rubros.values()) + PRECIO_MEDIDOR_BIDIRECCIONAL_COP)

    detalle = [
        {"rubro": f"Paneles ({paneles} × {precio_panel:,.0f} COP)".replace(",", "."), "valor_cop": costo_paneles},
        {"rubro": f"Inversor de referencia ({modelo_inversor})", "valor_cop": costo_inversor},
        {"rubro": "Estructura y anclajes", "valor_cop": rubros["estructura"]},
        {"rubro": "Protecciones eléctricas y cableado", "valor_cop": rubros["protecciones"]},
        {"rubro": "Mano de obra de instalación", "valor_cop": rubros["mano_obra"]},
        {"rubro": "Trámites ante el operador de red y certificación RETIE", "valor_cop": rubros["tramites"]},
        {"rubro": "Medidor bidireccional", "valor_cop": PRECIO_MEDIDOR_BIDIRECCIONAL_COP},
    ]

    costo_baterias = modulos_respaldo * PRECIO_BATERIA_5_12_KWH_COP
    diferencia_hibrido = max(0, PRECIO_INVERSOR_HIBRIDO_5KW_COP - costo_inversor) if inversor_kw <= 5 else None
    adicional_respaldo = costo_baterias + (diferencia_hibrido or 0)

    mercado_min = round(potencia_kwp * REFERENCIA_MERCADO_COP_KWP[0])
    mercado_max = round(potencia_kwp * REFERENCIA_MERCADO_COP_KWP[1])

    def retorno(valor):
        return round(valor / ahorro_anual_cop, 1) if ahorro_anual_cop > 0 else None

    return {
        "moneda": "COP",
        "fecha_precios": FECHA_PRECIOS,
        "detalle": detalle,
        "total_cop": total,
        "costo_por_kwp_cop": round(total / potencia_kwp),
        "referencia_mercado_kwp_cop": list(REFERENCIA_MERCADO_COP_KWP),
        "rango_mercado_cop": [mercado_min, mercado_max],
        "retorno_simple_anios": retorno(total),
        "retorno_rango_anios": [retorno(min(total, mercado_min)), retorno(max(total, mercado_max))],
        "respaldo_baterias": {
            "modulos": modulos_respaldo,
            "costo_baterias_cop": costo_baterias,
            "diferencia_inversor_hibrido_cop": diferencia_hibrido,
            "costo_adicional_cop": adicional_respaldo,
        },
        "mantenimiento_anual_cop": list(MANTENIMIENTO_ANUAL_COP),
        "notas": [
            "El estimado usa precios de equipos de tiendas en línea; los instaladores suelen cobrar más porque "
            "incluyen garantía, transporte y su utilidad. Por eso se muestra también el rango de mercado para un "
            "sistema instalado de este tamaño.",
            "Estructura, protecciones, mano de obra y trámites se estiman con su participación típica en el "
            "costo de un sistema residencial.",
            "No incluye los beneficios tributarios de la Ley 1715 de 2014 (deducción de renta y exclusión de IVA), "
            "que pueden reducir la inversión.",
            "El retorno simple divide la inversión entre el ahorro anual y no considera la venta de excedentes "
            "ni el aumento de la tarifa.",
        ],
        "fuentes": FUENTES,
    }
