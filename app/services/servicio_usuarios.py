from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm.exc import StaleDataError

from app.db.database import sesion_lectura, sesion_transaccional
from app.db.modelos import Ciudad, Usuario


class ConflictoDeVersion(Exception):
    pass


def a_diccionario(usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "email": usuario.correo,
        "telefono": usuario.telefono,
        "rol": usuario.rol.codigo,
        "ciudad": usuario.ciudad.nombre if usuario.ciudad else None,
        "ciudad_id": usuario.ciudad.codigo if usuario.ciudad else None,
        "consumo_mensual": usuario.consumo_mensual_kwh,
        "version": usuario.version,
        "created_at": usuario.creado_en,
        "updated_at": usuario.actualizado_en,
    }


def buscar_ciudad(sesion, texto: str | None) -> Ciudad | None:
    texto = (texto or "").strip()
    if not texto or texto.upper() == "N/A":
        return None
    ciudad = sesion.scalar(
        select(Ciudad).where(or_(Ciudad.codigo == texto.lower(), func.lower(Ciudad.nombre) == texto.lower()))
    )
    if ciudad is None:
        raise ValueError(f"La ciudad '{texto}' no está en el catálogo")
    return ciudad


def listar_usuarios() -> list[dict]:
    with sesion_lectura() as sesion:
        usuarios = sesion.scalars(select(Usuario).order_by(Usuario.creado_en.desc(), Usuario.id.desc())).all()
        return [a_diccionario(u) for u in usuarios]


def actualizar_usuario(
    usuario_id: int, nombre: str, ciudad: str | None, consumo_mensual: float, version: int | None = None
) -> dict:
    try:
        with sesion_transaccional() as sesion:
            usuario = sesion.get(Usuario, usuario_id)
            if usuario is None:
                raise ValueError("El usuario no existe")
            if version is not None and usuario.version != version:
                raise ConflictoDeVersion("Otro administrador modificó este usuario; recarga los datos")
            usuario.nombre = nombre.strip()
            usuario.ciudad = buscar_ciudad(sesion, ciudad)
            usuario.consumo_mensual_kwh = Decimal(str(consumo_mensual))
            sesion.flush()
            sesion.refresh(usuario)
            return {"message": "Usuario actualizado", **a_diccionario(usuario)}
    except StaleDataError as error:
        raise ConflictoDeVersion("Otro administrador modificó este usuario; recarga los datos") from error


def eliminar_usuario(usuario_id: int) -> dict:
    with sesion_transaccional() as sesion:
        usuario = sesion.get(Usuario, usuario_id)
        if usuario is None:
            raise ValueError("El usuario no existe")
        sesion.delete(usuario)
    return {"message": "Usuario eliminado"}
