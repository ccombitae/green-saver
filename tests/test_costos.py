"""Pruebas del costo estimado del sistema."""

from app.services.costos_service import PARTICIPACION, PRECIO_MEDIDOR_BIDIRECCIONAL_COP, estimar_costos, precio_inversor


def _costos(**kw):
    base = dict(paneles=5, potencia_panel_w=550, potencia_kwp=2.75, inversor_kw=3, modulos_respaldo=1, ahorro_anual_cop=2_550_000)
    base.update(kw)
    return estimar_costos(**base)


def test_total_es_la_suma_del_detalle():
    c = _costos()
    assert c["total_cop"] == sum(r["valor_cop"] for r in c["detalle"])


def test_rubros_porcentuales_respetan_su_participacion():
    c = _costos()
    total_sin_medidor = c["total_cop"] - PRECIO_MEDIDOR_BIDIRECCIONAL_COP
    mano_obra = next(r["valor_cop"] for r in c["detalle"] if r["rubro"].startswith("Mano de obra"))
    assert abs(mano_obra / total_sin_medidor - PARTICIPACION["mano_obra"]) < 0.001


def test_mas_paneles_cuesta_mas():
    assert _costos(paneles=10, potencia_kwp=5.5, inversor_kw=5)["total_cop"] > _costos()["total_cop"]


def test_inversor_usa_el_modelo_de_referencia_mas_cercano_hacia_arriba():
    kw, precio, _ = precio_inversor(3)
    assert kw >= 3 and precio > 0
    kw_grande, precio_grande, modelo = precio_inversor(30)
    assert kw_grande >= 30 and "×" in modelo


def test_retorno_y_rango_de_mercado():
    c = _costos()
    assert c["retorno_rango_anios"][0] <= c["retorno_simple_anios"] <= c["retorno_rango_anios"][1]
    assert c["rango_mercado_cop"][0] < c["rango_mercado_cop"][1]
    assert _costos(ahorro_anual_cop=0)["retorno_simple_anios"] is None


def test_respaldo_con_baterias_suma_baterias_e_inversor_hibrido():
    c = _costos(modulos_respaldo=2)
    r = c["respaldo_baterias"]
    assert r["costo_adicional_cop"] == r["costo_baterias_cop"] + (r["diferencia_inversor_hibrido_cop"] or 0)
    assert c["fuentes"] and c["fecha_precios"]
