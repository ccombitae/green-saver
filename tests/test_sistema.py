"""
PRUEBA DE SISTEMA (extremo a extremo de la API con base de datos real).

Recorre el flujo completo de negocio de Green Saver, en orden:
registro -> sesión -> cálculo con ML -> cotización -> aceptación -> sistema instalado.

Necesita una base de datos PostgreSQL VACÍA de pruebas (¡nunca la de producción!):

    # Windows PowerShell
    $env:TEST_DATABASE_URL="postgresql://usuario:clave@localhost:5432/greensaver_test"
    python -m pytest tests/test_sistema.py -v

Sin TEST_DATABASE_URL estas pruebas se omiten (skip).
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

TEST_DB = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="Define TEST_DATABASE_URL para la prueba de sistema")

SCHEMA = Path(__file__).resolve().parents[1] / "app" / "db" / "schema.sql"
USUARIO = {"name": "Ana Prueba", "phone": "3001234567", "email": "ana.sistema@prueba.com", "password": "Clave123*"}
MATERIALES = {
    "panelType": "Monocristalino 550W",
    "inverterType": "Inversor Hibrido 5kW",
    "batteryType": "Sin bateria",
    "structureType": "Estructura coplanar aluminio",
}


@pytest.fixture(scope="module")
def ctx():
    """Base de datos limpia + cliente HTTP. Comparte estado entre los pasos del flujo."""
    import psycopg2

    original = settings.database_url
    settings.database_url = TEST_DB
    with psycopg2.connect(TEST_DB) as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS cotizaciones, sistemas_instalados, calculos_sistema, usuarios CASCADE")
        cur.execute(SCHEMA.read_text(encoding="utf-8"))
    yield {"c": TestClient(app)}
    settings.database_url = original


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_cp01_registro_de_usuario(ctx):
    r = ctx["c"].post("/auth/register", json=USUARIO)
    assert r.status_code == 201
    assert r.json()["role"] == "user" and r.json()["access_token"]


def test_cp01b_registro_no_permite_crear_administradores(ctx):
    """Regresión del bug B-10: el registro público aceptaba role=admin."""
    r = ctx["c"].post("/auth/register", json={**USUARIO, "email": "intruso@prueba.com", "role": "admin"})
    assert r.status_code == 201
    assert r.json()["role"] == "user"


def test_cp02_registro_duplicado_es_rechazado(ctx):
    assert ctx["c"].post("/auth/register", json=USUARIO).status_code == 400


def test_cp03_login_con_clave_incorrecta_da_401(ctx):
    r = ctx["c"].post("/auth/login", json={"email": USUARIO["email"], "password": "incorrecta"})
    assert r.status_code == 401


def test_cp04_login_correcto_entrega_tokens(ctx):
    r = ctx["c"].post("/auth/login", json={"email": USUARIO["email"], "password": USUARIO["password"]})
    assert r.status_code == 200
    ctx["token"], ctx["refresh"] = r.json()["access_token"], r.json()["refresh_token"]


def test_cp05_perfil_del_usuario_autenticado(ctx):
    r = ctx["c"].get("/auth/me", headers=bearer(ctx["token"]))
    assert r.status_code == 200 and r.json()["email"] == USUARIO["email"]


def test_cp06_refresco_de_sesion(ctx):
    r = ctx["c"].post("/auth/refresh", json={"refreshToken": ctx["refresh"]})
    assert r.status_code == 200 and r.json()["access_token"]


def test_cp07_estimacion_con_modelo_de_ml(ctx):
    r = ctx["c"].post("/ml/estimar", json={"consumo_mensual_kwh": 250, "ciudad_id": "girardot"})
    assert r.status_code == 200
    ctx["estimacion"] = r.json()
    assert ctx["estimacion"]["paneles"] >= 1


def test_cp08_guardar_calculo(ctx):
    e = ctx["estimacion"]
    r = ctx["c"].post(
        "/calculos",
        headers=bearer(ctx["token"]),
        json={
            "email": USUARIO["email"],
            "consumption": 250,
            "estimatedPanels": e["paneles"],
            "coverage": e["cobertura_anual_pct"],
            "estimatedSavings": 250,
            "recommendation": e["recomendacion"],
        },
    )
    assert r.status_code == 200
    ctx["calculo_id"] = r.json()["id"]


def test_cp09_historial_devuelve_campos_en_camelcase(ctx):
    """Regresión del bug B-02: antes llegaba 'estimatedpanels' y la app mostraba vacío."""
    r = ctx["c"].get("/calculos", headers=bearer(ctx["token"]))
    assert r.status_code == 200
    fila = r.json()[0]
    assert fila["estimatedPanels"] == ctx["estimacion"]["paneles"]
    assert "estimatedpanels" not in fila


def test_cp10_usuario_no_accede_a_rutas_de_administrador(ctx):
    assert ctx["c"].get("/usuarios", headers=bearer(ctx["token"])).status_code == 403


def test_cp11_login_de_administrador(ctx):
    from app.services.auth_service import ADMIN_EMAIL, ADMIN_PASSWORD

    r = ctx["c"].post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200 and r.json()["role"] == "admin"
    ctx["admin"] = r.json()["access_token"]


def test_cp12_otro_usuario_no_ve_calculos_ajenos(ctx):
    """Regresión del bug B-03: antes cualquier usuario veía los cálculos de todos."""
    otro = {**USUARIO, "email": "otro.sistema@prueba.com"}
    token = ctx["c"].post("/auth/register", json=otro).json()["access_token"]
    assert ctx["c"].get("/calculos", headers=bearer(token)).json() == []
    assert len(ctx["c"].get("/calculos", headers=bearer(ctx["admin"])).json()) == 1


def test_cp13_administrador_lista_usuarios(ctx):
    r = ctx["c"].get("/usuarios", headers=bearer(ctx["admin"]))
    assert r.status_code == 200
    assert USUARIO["email"] in [u["email"] for u in r.json()]


def test_cp14_enviar_cotizacion(ctx):
    r = ctx["c"].post(
        "/quotes/send",
        headers=bearer(ctx["admin"]),
        json={
            "calculationId": ctx["calculo_id"],
            "clientEmail": USUARIO["email"],
            "clientName": USUARIO["name"],
            "totalPrice": 12500000,
            "notes": "Prueba de sistema",
            "materials": MATERIALES,
        },
    )
    assert r.status_code == 200
    datos = r.json()["data"]
    # Sin servidor SMTP configurado la cotización igual queda guardada (estado failed)
    assert datos["status"] in {"sent", "failed"}
    ctx["cotizacion_id"] = datos["id"]


def test_cp15_aceptar_cotizacion_crea_sistema(ctx):
    r = ctx["c"].post(
        f"/quotes/{ctx['cotizacion_id']}/accept",
        headers=bearer(ctx["admin"]),
        json={"installDate": "2026-11-15"},
    )
    assert r.status_code == 200 and r.json()["data"]["status"] == "accepted"


def test_cp16_usuario_ve_su_sistema_instalado(ctx):
    r = ctx["c"].get("/systems", headers=bearer(ctx["token"]))
    assert r.status_code == 200
    sistema = r.json()["data"][0]
    assert sistema["inverter"] == MATERIALES["inverterType"]


def test_cp17_recuperar_contrasena_y_entrar_con_la_nueva(ctx):
    r = ctx["c"].post("/auth/recover-password", json={"email": USUARIO["email"], "newPassword": "Nueva456*"})
    assert r.status_code == 200
    r = ctx["c"].post("/auth/login", json={"email": USUARIO["email"], "password": "Nueva456*"})
    assert r.status_code == 200
