from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request

from app.core.security import is_admin_role
from app.schemas.solar import CalculoCrear
from app.services.servicio_calculos import (
    crear_calculo,
    eliminar_calculo,
    estadisticas_mensuales,
    listar_calculos,
    reporte_general,
)

router = APIRouter(prefix="/calculos", tags=["Calculos"])


def credenciales(request: Request) -> dict:
    return getattr(request.state, "auth", {}) or {}


@router.get("")
async def obtener_calculos(request: Request):
    datos = credenciales(request)
    try:
        if is_admin_role(datos.get("role")):
            return listar_calculos()
        return listar_calculos(correo=datos.get("email"))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("")
async def guardar_calculo(calculo: CalculoCrear, request: Request):
    datos = credenciales(request)
    try:
        return crear_calculo(calculo, datos.get("email"), is_admin_role(datos.get("role")))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/reporte")
async def obtener_reporte():
    try:
        return reporte_general()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/estadisticas")
async def obtener_estadisticas(desde: date | None = None, hasta: date | None = None):
    hasta = hasta or date.today()
    desde = desde or (hasta - timedelta(days=365))
    try:
        return estadisticas_mensuales(desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.delete("/{calculo_id}")
async def borrar_calculo(calculo_id: int, request: Request):
    if not is_admin_role(credenciales(request).get("role")):
        raise HTTPException(status_code=403, detail="Solo el administrador puede eliminar cálculos")
    try:
        return eliminar_calculo(calculo_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
