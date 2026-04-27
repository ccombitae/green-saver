from fastapi import APIRouter, HTTPException

from app.schemas.quotes import QuoteSendRequest
from app.services.quote_service import (
    list_quote_calculations,
    list_quote_options,
    list_sent_quotes,
    send_quote,
)

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.get("/calculations")
def get_quote_calculations():
    return {"success": True, "data": list_quote_calculations()}


@router.get("/options")
def get_quote_options():
    return {"success": True, "data": list_quote_options()}


@router.get("")
def get_sent_quotes():
    return {"success": True, "data": list_sent_quotes()}


@router.post("/send")
def post_send_quote(payload: QuoteSendRequest):
    try:
        data = send_quote(payload)
        return {"success": True, "message": "Cotizacion enviada correctamente", "data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error enviando cotizacion: {exc}") from exc
