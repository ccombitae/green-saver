"""Pruebas unitarias del dimensionamiento y del predictor."""

import json
import math

import pytest

from app.ml import predictor
from app.services.estimation_service import energia_panel_mes, estimar_sistema


# ---------------------------------------------------------------- fórmula base
def test_energia_de_un_panel_en_un_mes():
    # 550 W x 5 HSP x 30 días x 0.8 = 66 kWh
    assert energia_panel_mes(550, 5.0, 30, 0.8) == pytest.approx(66.0)


def test_consumo_cero_o_negativo_es_rechazado(sin_artefactos):
    with pytest.raises(ValueError):
        estimar_sistema(0, "girardot")


# ------------------------------------------------------- sin modelo (respaldo)
def test_sin_artefactos_usa_valor_de_respaldo(sin_artefactos):
    resultado = estimar_sistema(300, "cualquiera")
    assert resultado["fuente_hsp"] == "respaldo"
    assert resultado["hsp_promedio"] == predictor.HSP_RESPALDO
    assert "aproximada" in resultado["recomendacion"]


def test_paneles_es_el_techo_del_consumo_entre_la_energia_por_panel(sin_artefactos):
    resultado = estimar_sistema(300, None)
    energia_promedio = sum(m["generacion_kwh"] for m in resultado["detalle_mensual"]) / 12 / resultado["paneles"]
    assert resultado["paneles"] == math.ceil(300 / energia_promedio - 1e-6)


def test_cobertura_nunca_supera_100(sin_artefactos):
    resultado = estimar_sistema(150, None)
    assert all(0 < m["cobertura_pct"] <= 100 for m in resultado["detalle_mensual"])
    assert 0 < resultado["cobertura_anual_pct"] <= 100


def test_mas_consumo_requiere_mas_paneles(sin_artefactos):
    assert estimar_sistema(600, None)["paneles"] > estimar_sistema(200, None)["paneles"]


def test_paneles_mas_potentes_requieren_menos_unidades(sin_artefactos):
    assert estimar_sistema(500, None, potencia_panel_w=600)["paneles"] < estimar_sistema(500, None, potencia_panel_w=300)["paneles"]


def test_ahorro_usa_la_tarifa(sin_artefactos):
    a = estimar_sistema(300, None, tarifa_kwh_cop=800)
    b = estimar_sistema(300, None, tarifa_kwh_cop=1600)
    assert b["ahorro_anual_cop"] == pytest.approx(2 * a["ahorro_anual_cop"], rel=0.01)


# ------------------------------------------------------- con modelo entrenado
def test_entrenamiento_genera_los_artefactos(con_modelo):
    for archivo in ("modelo_hsp.joblib", "climatologia.csv", "metadata.json", "eda_dashboard.json"):
        assert (con_modelo / archivo).exists(), archivo
    metadata = json.loads((con_modelo / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["modelo"] in {"Regresión lineal", "Random Forest", "Gradient Boosting"}
    assert "Línea base (promedio del mes)" in metadata["metricas_validacion"]


def test_prediccion_con_modelo_devuelve_12_meses(con_modelo):
    resultado = predictor.predecir_hsp_mensual("girardot")
    assert resultado["fuente"] == "modelo"
    assert len(resultado["hsp_mensual"]) == 12
    assert all(1 < h < 9 for h in resultado["hsp_mensual"])


def test_ciudad_desconocida_lanza_error(con_modelo):
    with pytest.raises(predictor.CiudadNoEncontrada):
        predictor.predecir_hsp_mensual("ciudad_inexistente")


def test_ciudad_soleada_necesita_menos_paneles_que_ciudad_nublada(con_modelo):
    soleada = estimar_sistema(400, "riohacha")
    nublada = estimar_sistema(400, "quibdo")
    assert soleada["hsp_promedio"] > nublada["hsp_promedio"]
    assert soleada["paneles"] <= nublada["paneles"]


def test_girardot_aparece_primero_en_el_catalogo(con_modelo):
    assert predictor.listar_ciudades()[0]["id"] == "girardot"
