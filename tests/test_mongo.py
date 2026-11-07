import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import documentos
from app.main import app
from app.services.servicio_autenticacion import CONTRASENA_ADMINISTRADOR, CORREO_ADMINISTRADOR

URL_MONGO = os.getenv("MONGO_URL_PRUEBAS")
cliente = TestClient(app)


@pytest.fixture
def mongo(monkeypatch, con_modelo):
    if not URL_MONGO:
        pytest.skip("Define MONGO_URL_PRUEBAS para las pruebas con MongoDB")
    monkeypatch.setattr(settings, "mongo_url", URL_MONGO)
    monkeypatch.setattr(settings, "mongo_bd", "green_saver_pruebas")
    coleccion = documentos.coleccion_estimaciones()
    coleccion.delete_many({})
    yield coleccion
    coleccion.delete_many({})


def token_administrador() -> dict:
    respuesta = cliente.post("/auth/login", json={"email": CORREO_ADMINISTRADOR, "password": CONTRASENA_ADMINISTRADOR})
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


def test_estimar_guarda_el_documento_completo(mongo):
    respuesta = cliente.post("/ml/estimar", json={"consumo_mensual_kwh": 250, "ciudad_id": "girardot"})
    assert respuesta.status_code == 200
    identificador = respuesta.json()["estimacion_id"]
    documento = cliente.get(f"/ml/estimaciones/{identificador}", headers=token_administrador()).json()
    assert documento["ciudad"]["id"] == "girardot"
    assert len(documento["detalle_mensual"]) == 12
    assert documento["resumen"]["paneles"] == respuesta.json()["paneles"]


def test_estadisticas_agrupan_por_ciudad(mongo):
    for ciudad, consumo in (("girardot", 200), ("girardot", 300), ("riohacha", 250)):
        cliente.post("/ml/estimar", json={"consumo_mensual_kwh": consumo, "ciudad_id": ciudad})
    filas = cliente.get("/ml/estimaciones/estadisticas", headers=token_administrador()).json()
    assert [(f["ciudad_id"], f["estimaciones"]) for f in filas] == [("girardot", 2), ("riohacha", 1)]
    assert filas[0]["consumo_promedio_kwh"] == 250


def test_estadisticas_son_solo_para_el_administrador(mongo):
    assert cliente.get("/ml/estimaciones/estadisticas").status_code == 401


def test_la_consulta_por_ciudad_usa_el_indice(mongo):
    cliente.post("/ml/estimar", json={"consumo_mensual_kwh": 250, "ciudad_id": "girardot"})
    plan = mongo.find({"ciudad.id": "girardot"}).sort("creado_en", -1).explain()
    assert "ix_ciudad_fecha" in str(plan["queryPlanner"]["winningPlan"])


def test_sin_mongo_la_estimacion_sigue_funcionando(monkeypatch, con_modelo):
    monkeypatch.setattr(settings, "mongo_url", "")
    respuesta = cliente.post("/ml/estimar", json={"consumo_mensual_kwh": 250, "ciudad_id": "girardot"})
    assert respuesta.status_code == 200 and respuesta.json()["estimacion_id"] is None


def test_con_mongo_caido_la_estimacion_sigue_funcionando(monkeypatch, con_modelo):
    monkeypatch.setattr(settings, "mongo_url", "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=300")
    respuesta = cliente.post("/ml/estimar", json={"consumo_mensual_kwh": 250, "ciudad_id": "girardot"})
    assert respuesta.status_code == 200 and respuesta.json()["estimacion_id"] is None
