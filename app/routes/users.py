from fastapi import APIRouter, HTTPException

from app.services.user_service import create_user, delete_user, list_users, update_user


router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get("")
async def get_usuarios():
    try:
        return list_users()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("")
async def insert_usuario(nombre: str, ciudad: str, consumo_mensual: float):
    try:
        return create_user(nombre, ciudad, consumo_mensual)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/{user_id}")
async def update_usuario(user_id: int, nombre: str, ciudad: str, consumo_mensual: float):
    try:
        return update_user(user_id, nombre, ciudad, consumo_mensual)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{user_id}")
async def delete_usuario(user_id: int):
    try:
        return delete_user(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
