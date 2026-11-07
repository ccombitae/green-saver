from fastapi import APIRouter, HTTPException

from app.schemas.quotes import QuoteAcceptRequest, QuoteSendRequest
from app.services.servicio_cotizaciones import (
    aceptar_cotizacion,
    calculos_cotizables,
    enviar_cotizacion,
    listar_cotizaciones,
    opciones_de_cotizacion,
)

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.get("/calculations")
def get_quote_calculations():
    return {"success": True, "data": calculos_cotizables()}


@router.get("/options")
def get_quote_options():
    return {"success": True, "data": opciones_de_cotizacion()}


@router.get("")
def get_sent_quotes():
    return {"success": True, "data": listar_cotizaciones()}


@router.post("/send")
def post_send_quote(payload: QuoteSendRequest):
    try:
        data = enviar_cotizacion(payload)
        message = "Cotizacion enviada correctamente"
        if data.get("status") != "sent":
            message = "Cotizacion guardada, pero no se pudo enviar el correo"
        return {"success": True, "message": message, "data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error enviando cotizacion: {exc}") from exc


@router.post("/{quote_id}/accept")
def post_accept_quote(quote_id: int, payload: QuoteAcceptRequest):
    try:
        data = aceptar_cotizacion(quote_id, payload.installDate)
        return {"success": True, "message": "Cotizacion aceptada y sistema guardado", "data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error aceptando cotizacion: {exc}") from exc
