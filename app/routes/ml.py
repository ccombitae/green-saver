"""
Endpoints del módulo de Machine Learning.

    GET  /ml/ciudades  catálogo de ciudades con datos solares
    POST /ml/estimar   dimensiona el sistema solar usando las HSP que predice el modelo
    GET  /ml/modelo    información del modelo: algoritmo, métricas, fecha de entrenamiento
    GET  /ml/eda       datos agregados del análisis exploratorio para el dashboard

Son públicos (no exponen datos personales) para que también funcionen en el
"Cálculo rápido" de la pantalla de login.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request

from app.core.security import decode_bearer_token, is_admin_role
from app.db import documentos
from app.ml import predictor
from app.schemas.ml import EstimacionSolicitud
from app.services.estimation_service import estimar_sistema

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.get("/ciudades")
async def get_ciudades():
    return predictor.listar_ciudades()


def correo_opcional(request: Request) -> str | None:
    try:
        return decode_bearer_token(request.headers.get("Authorization")).get("email")
    except ValueError:
        return None


@router.post("/estimar")
async def post_estimar(solicitud: EstimacionSolicitud, request: Request):
    try:
        resultado = estimar_sistema(
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
    resultado["estimacion_id"] = documentos.guardar_estimacion(solicitud.model_dump(), resultado, correo_opcional(request))
    return resultado


@router.get("/estimaciones")
async def obtener_estimaciones(request: Request, limite: int = 20):
    datos = getattr(request.state, "auth", {}) or {}
    usuario = None if is_admin_role(datos.get("role")) else datos.get("email")
    try:
        return documentos.estimaciones_recientes(usuario, max(1, min(limite, 100)))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/estimaciones/estadisticas")
async def obtener_estadisticas_estimaciones(dias: int | None = None):
    desde = datetime.now(timezone.utc) - timedelta(days=dias) if dias else None
    try:
        return documentos.estadisticas_por_ciudad(desde)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/estimaciones/{estimacion_id}")
async def obtener_estimacion(estimacion_id: str, request: Request):
    datos = getattr(request.state, "auth", {}) or {}
    try:
        documento = documentos.obtener_estimacion(estimacion_id)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if documento is None or (not is_admin_role(datos.get("role")) and documento.get("usuario") not in (None, datos.get("email"))):
        raise HTTPException(status_code=404, detail="Estimación no encontrada")
    return documento


@router.get("/modelo")
async def get_modelo():
    return predictor.metadata()


@router.get("/eda")
async def get_eda():
    datos = predictor.datos_eda()
    if datos is None:
        raise HTTPException(status_code=404, detail="Aún no se ha ejecutado el análisis exploratorio (ml/eda.py)")
    return datos
