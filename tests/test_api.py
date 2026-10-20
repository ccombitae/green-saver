"""
Pruebas de los endpoints con el cliente de pruebas de FastAPI.
No necesitan base de datos: cubren el módulo /ml y el middleware de seguridad.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app

cliente = TestClient(app)


def token_de(rol: str) -> dict:
    token, _ = create_access_token({"id": 1, "email": f"{rol}@prueba.com", "name": rol, "role": rol})
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ módulo ML
def test_listar_ciudades(con_modelo):
    respuesta = cliente.get("/ml/ciudades")
    assert respuesta.status_code == 200
    ids = [c["id"] for c in respuesta.json()]
    assert "girardot" in ids and "bogota" in ids


def test_estimar_sistema_ok(con_modelo):
    respuesta = cliente.post("/ml/estimar", json={"consumo_mensual_kwh": 250, "ciudad_id": "girardot"})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["fuente_hsp"] == "modelo"
    assert cuerpo["paneles"] >= 1
    assert len(cuerpo["detalle_mensual"]) == 12
    assert cuerpo["ciudad"]["nombre"] == "Girardot"


def test_estimar_ciudad_inexistente_da_404(con_modelo):
    respuesta = cliente.post("/ml/estimar", json={"consumo_mensual_kwh": 250, "ciudad_id": "atlantida"})
    assert respuesta.status_code == 404


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"consumo_mensual_kwh": -5, "ciudad_id": "girardot"},
        {"consumo_mensual_kwh": 0, "ciudad_id": "girardot"},
        {"consumo_mensual_kwh": "mucho", "ciudad_id": "girardot"},
        {"ciudad_id": "girardot"},
        {"consumo_mensual_kwh": 250, "ciudad_id": "girardot", "potencia_panel_w": 5000},
    ],
)
def test_estimar_valida_la_entrada(con_modelo, cuerpo):
    assert cliente.post("/ml/estimar", json=cuerpo).status_code == 422


def test_info_del_modelo(con_modelo):
    cuerpo = cliente.get("/ml/modelo").json()
    assert cuerpo["estado"] == "entrenado"
    assert "metricas_validacion" in cuerpo


def test_info_del_modelo_sin_entrenar(sin_artefactos):
    assert cliente.get("/ml/modelo").json()["estado"] == "sin entrenar"


def test_datos_eda_para_dashboard(con_modelo):
    cuerpo = cliente.get("/ml/eda").json()
    assert len(cuerpo["ranking_ciudades"]) > 0
    assert len(cuerpo["perfil_mensual_nacional"]) == 12


def test_eda_sin_ejecutar_da_404(sin_artefactos):
    assert cliente.get("/ml/eda").status_code == 404


# ------------------------------------------------- middleware JWT + roles
def test_ruta_protegida_sin_token_da_401():
    assert cliente.get("/calculos").status_code == 401


def test_token_falso_da_401():
    assert cliente.get("/calculos", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_usuario_normal_no_entra_a_rutas_de_admin():
    assert cliente.get("/usuarios", headers=token_de("user")).status_code == 403
    assert cliente.get("/quotes", headers=token_de("user")).status_code == 403


def test_raiz_es_publica():
    assert cliente.get("/").status_code == 200
