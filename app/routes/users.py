from fastapi import APIRouter, HTTPException

from app.services.servicio_usuarios import ConflictoDeVersion, actualizar_usuario, eliminar_usuario, listar_usuarios

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get("")
async def obtener_usuarios():
    try:
        return listar_usuarios()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.put("/{usuario_id}")
async def modificar_usuario(
    usuario_id: int, nombre: str, consumo_mensual: float, ciudad: str | None = None, version: int | None = None
):
    try:
        return actualizar_usuario(usuario_id, nombre, ciudad, consumo_mensual, version)
    except ConflictoDeVersion as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.delete("/{usuario_id}")
async def borrar_usuario(usuario_id: int):
    try:
        return eliminar_usuario(usuario_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
