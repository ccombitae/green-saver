from fastapi import APIRouter, HTTPException

from app.schemas.solar import CalculoCrear
from app.services.solar_service import create_calculo, delete_calculo, list_calculos, report_general, update_calculo


router = APIRouter(prefix="/calculos", tags=["Calculos"])


@router.get("")
async def get_calculos():
    try:
        return list_calculos()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("")
async def insert_calculo_v2(calculo: CalculoCrear):
    try:
        return create_calculo(calculo)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/{calculo_id}")
async def update_calculo_route(
    calculo_id: int,
    usuario_id: int,
    panel_id: int,
    inversor_id: int,
    bateria_id: int,
    paneles_necesarios: int,
    inversor_kw: float,
    bateria_kwh: float,
    costo_total: float,
):
    try:
        return update_calculo(
            calculo_id,
            usuario_id,
            panel_id,
            inversor_id,
            bateria_id,
            paneles_necesarios,
            inversor_kw,
            bateria_kwh,
            costo_total,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{calculo_id}")
async def delete_calculo_route(calculo_id: int):
    try:
        return delete_calculo(calculo_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/reporte")
async def reporte_general_route():
    try:
        return report_general()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
