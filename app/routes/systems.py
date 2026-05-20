from fastapi import APIRouter, HTTPException, Request

from app.core.security import is_admin_role
from app.schemas.systems import SystemAssignRequest
from app.services.system_service import assign_system, list_systems


router = APIRouter(prefix="/systems", tags=["Systems"])


@router.get("")
async def get_systems(request: Request, email: str | None = None):
    try:
        auth = getattr(request.state, "auth", {}) or {}
        token_email = auth.get("email")
        token_role = auth.get("role")

        target_email = email or token_email
        if not target_email:
            raise HTTPException(status_code=400, detail="Email requerido")

        if email and email.lower() != (token_email or "").lower() and not is_admin_role(token_role):
            raise HTTPException(status_code=403, detail="No tienes permisos para consultar otros sistemas")

        return {"success": True, "data": list_systems(target_email)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/assign")
async def post_assign_system(payload: SystemAssignRequest):
    try:
        return {"success": True, "message": "Sistema asignado", "data": assign_system(payload)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc