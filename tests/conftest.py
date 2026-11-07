import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.ml import predictor  # noqa: E402
from tests.datos_sinteticos import escribir_csv_sintetico  # noqa: E402


@pytest.fixture(scope="session")
def carpeta_entrenada(tmp_path_factory) -> Path:
    """Ejecuta EDA + entrenamiento reales sobre datos sintéticos, una vez por sesión."""
    base = tmp_path_factory.mktemp("ml")
    datos = escribir_csv_sintetico(base / "datos.csv")
    artefactos = base / "artifacts"
    reportes = base / "reports"
    for script in ("eda.py", "entrenar.py"):
        subprocess.run(
            [sys.executable, str(RAIZ / "ml" / script), "--datos", str(datos),
             "--artefactos", str(artefactos), "--reportes", str(reportes), "--sin-figuras"],
            check=True, capture_output=True, text=True,
        )
    return base


@pytest.fixture
def con_modelo(carpeta_entrenada, monkeypatch):
    """La API usa los artefactos entrenados con datos sintéticos."""
    monkeypatch.setattr(predictor, "CARPETA_ARTEFACTOS", carpeta_entrenada / "artifacts")
    predictor.recargar()
    yield carpeta_entrenada / "artifacts"
    predictor.recargar()


@pytest.fixture
def sin_artefactos(tmp_path, monkeypatch):
    """La API sin ningún artefacto (servidor recién desplegado sin entrenar)."""
    monkeypatch.setattr(predictor, "CARPETA_ARTEFACTOS", tmp_path / "vacia")
    predictor.recargar()
    yield
    predictor.recargar()


def reiniciar_base_de_datos(url: str) -> None:
    import psycopg2

    from app.db.migrar import aplicar_migraciones

    with psycopg2.connect(url) as conexion, conexion.cursor() as cursor:
        cursor.execute("DROP SCHEMA IF EXISTS legado CASCADE")
        cursor.execute("DROP SCHEMA public CASCADE")
        cursor.execute("CREATE SCHEMA public")
    aplicar_migraciones()


@pytest.fixture(scope="module")
def base_de_datos():
    """Base de datos PostgreSQL de pruebas, vacía y con todas las migraciones aplicadas."""
    from app.core.config import settings

    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Define TEST_DATABASE_URL para las pruebas con base de datos")
    original = settings.database_url
    settings.database_url = url
    reiniciar_base_de_datos(url)
    yield url
    settings.database_url = original
