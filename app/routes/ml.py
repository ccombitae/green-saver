"""
Endpoints del módulo de Machine Learning.

    GET  /ml/ciudades  catálogo de ciudades con datos solares
    POST /ml/estimar   dimensiona el sistema solar usando las HSP que predice el modelo
    GET  /ml/modelo    información del modelo: algoritmo, métricas, fecha de entrenamiento
    GET  /ml/eda       datos agregados del análisis exploratorio para el dashboard

Son públicos (no exponen datos personales) para que también funcionen en el
"Cálculo rápido" de la pantalla de login.
"""

from fastapi import APIRouter, HTTPException

from app.ml import predictor
from app.schemas.ml import EstimacionSolicitud
from app.services.estimation_service import estimar_sistema

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.get("/ciudades")
async def get_ciudades():
    return predictor.listar_ciudades()


@router.post("/estimar")
async def post_estimar(solicitud: EstimacionSolicitud):
    try:
        return estimar_sistema(
            consumo_mensual_kwh=solicitud.consumo_mensual_kwh,
            ciudad_id=solicitud.ciudad_id,
            potencia_panel_w=solicitud.potencia_panel_w,
            rendimiento=solicitud.rendimiento,
            tarifa_kwh_cop=solicitud.tarifa_kwh_cop,
        )
    except predictor.CiudadNoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/modelo")
async def get_modelo():
    return predictor.metadata()


@router.get("/eda")
async def get_eda():
    datos = predictor.datos_eda()
    if datos is None:
        raise HTTPException(status_code=404, detail="Aún no se ha ejecutado el análisis exploratorio (ml/eda.py)")
    return datos
