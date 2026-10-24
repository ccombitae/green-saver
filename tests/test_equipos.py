"""Pruebas de la recomendación de inversor, baterías e instalación."""

from app.services.equipos_service import (
    BATERIA_MODULO_KWH,
    recomendar_baterias,
    recomendar_instalacion,
    recomendar_inversor,
)


def test_inversor_respeta_la_relacion_dc_ac():
    inv = recomendar_inversor(2.75)
    assert inv["potencia_kw"] == 3
    assert inv["relacion_dc_ac"] <= 1.25


def test_inversor_puede_ser_menor_que_los_paneles():
    # 5,5 kWp / 1,25 = 4,4 kW mínimo -> 5 kW comercial
    assert recomendar_inversor(5.5)["potencia_kw"] == 5


def test_inversor_grande_es_trifasico():
    inv = recomendar_inversor(16.5)
    assert inv["potencia_kw"] >= 15 and inv["conexion"] == "Trifásico"


def test_baterias_respaldo_menor_que_autonomia():
    b = recomendar_baterias(300)
    assert b["respaldo_nocturno"]["capacidad_kwh"] < b["autonomia_un_dia"]["capacidad_kwh"]
    assert b["autonomia_un_dia"]["capacidad_instalada_kwh"] >= b["autonomia_un_dia"]["capacidad_kwh"]
    assert b["autonomia_un_dia"]["capacidad_instalada_kwh"] == round(b["autonomia_un_dia"]["modulos"] * BATERIA_MODULO_KWH, 2)


def test_instalacion_area_peso_e_inclinacion():
    i = recomendar_instalacion(paneles=5, potencia_panel_w=550, latitud=4.3)
    assert 12 < i["area_paneles_m2"] < 14
    assert i["area_techo_recomendada_m2"] > i["area_paneles_m2"]
    assert i["inclinacion_grados"] == 10  # latitud baja: mínimo de 10°
    assert i["orientacion"] == "Hacia el sur"
    assert 10 < i["carga_kg_m2"] < 20


def test_inclinacion_sigue_la_latitud_en_el_norte():
    assert recomendar_instalacion(4, 550, latitud=11.5)["inclinacion_grados"] == 12


def test_estimacion_incluye_equipos_sin_modelo(sin_artefactos):
    from app.services.estimation_service import estimar_sistema

    r = estimar_sistema(250, None)
    assert r["inversor"]["potencia_kw"] >= 1.5
    assert r["baterias"]["opcional"] is True
    assert r["instalacion"]["orientacion"].startswith("Hacia el ecuador")
    assert r["rendimiento_especifico_kwh_kwp"] > 0


def test_estimacion_con_ciudad_usa_su_latitud(con_modelo):
    from app.services.estimation_service import estimar_sistema

    r = estimar_sistema(250, "girardot")
    assert r["instalacion"]["orientacion"] == "Hacia el sur"
    assert r["area_aprox_m2"] == r["instalacion"]["area_paneles_m2"]
