import os
import secrets

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token, create_refresh_token, decode_token
from app.db.database import sesion_lectura, sesion_transaccional
from app.db.modelos import Rol, Usuario
from app.schemas.auth import PasswordRecoveryRequest, RefreshTokenRequest, UsuarioLogin, UsuarioRegistro

contexto_contrasenas = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")
CORREO_ADMINISTRADOR = "admin@greensaver.com"
CONTRASENA_ADMINISTRADOR = os.getenv("ADMIN_PASSWORD", "admin")


def normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


def nombre_visible(correo: str) -> str:
    local = correo.split("@")[0]
    partes = local.replace(".", " ").replace("_", " ").replace("-", " ").split()
    return " ".join(parte.capitalize() for parte in partes) or "Usuario"


def usuario_administrador() -> dict:
    return {"id": 0, "email": CORREO_ADMINISTRADOR, "name": "Administrador", "phone": None, "role": "admin"}


def contrasena_hash(contrasena: str) -> str:
    return contexto_contrasenas.hash(contrasena)


def verificar_contrasena(contrasena: str, almacenada: str) -> bool:
    if not almacenada or not almacenada.startswith("$"):
        return False
    try:
        return contexto_contrasenas.verify(contrasena, almacenada)
    except Exception:
        return False


def emitir_tokens(usuario: dict) -> dict:
    acceso, expira_acceso = create_access_token(usuario)
    refresco, expira_refresco = create_refresh_token(usuario)
    return {
        "access_token": acceso,
        "refresh_token": refresco,
        "token_type": "bearer",
        "expires_in": expira_acceso,
        "refresh_expires_in": expira_refresco,
    }


def respuesta_usuario(usuario: dict) -> dict:
    return {
        "id": usuario["id"],
        "email": usuario["email"],
        "name": usuario["name"],
        "phone": usuario.get("phone"),
        "role": usuario["role"],
        **emitir_tokens(usuario),
    }


def a_diccionario(usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "email": usuario.correo,
        "name": usuario.nombre or nombre_visible(usuario.correo),
        "phone": usuario.telefono,
        "role": usuario.rol.codigo,
    }


def buscar_por_correo(sesion, correo: str) -> Usuario | None:
    return sesion.scalar(select(Usuario).where(Usuario.correo == normalizar_correo(correo)))


def registrar_usuario(datos: UsuarioRegistro) -> dict:
    correo = normalizar_correo(datos.email)
    try:
        with sesion_transaccional() as sesion:
            if buscar_por_correo(sesion, correo):
                raise ValueError("El usuario ya existe")
            rol = sesion.scalar(select(Rol).where(Rol.codigo == "user"))
            usuario = Usuario(
                nombre=datos.name.strip(),
                correo=correo,
                telefono=datos.phone.strip(),
                contrasena_hash=contrasena_hash(datos.password),
                rol=rol,
            )
            sesion.add(usuario)
            sesion.flush()
            resultado = a_diccionario(usuario)
    except IntegrityError as error:
        raise ValueError("El usuario ya existe") from error
    return respuesta_usuario(resultado)


def iniciar_sesion(credenciales: UsuarioLogin) -> dict:
    correo = normalizar_correo(credenciales.email)
    if correo == CORREO_ADMINISTRADOR:
        if secrets.compare_digest(credenciales.password.encode(), CONTRASENA_ADMINISTRADOR.encode()):
            return respuesta_usuario(usuario_administrador())
        raise ValueError("Credenciales incorrectas")

    with sesion_lectura() as sesion:
        usuario = buscar_por_correo(sesion, correo)
        if not usuario or not verificar_contrasena(credenciales.password, usuario.contrasena_hash):
            raise ValueError("Credenciales incorrectas")
        resultado = a_diccionario(usuario)
    return respuesta_usuario(resultado)


def usuario_actual(correo: str | None = None, datos_token: dict | None = None) -> dict:
    correo = normalizar_correo((datos_token or {}).get("email") or correo or "")
    if correo == CORREO_ADMINISTRADOR:
        return usuario_administrador()
    with sesion_lectura() as sesion:
        usuario = buscar_por_correo(sesion, correo)
        if not usuario:
            raise ValueError("Usuario no encontrado")
        return a_diccionario(usuario)


def renovar_sesion(datos: RefreshTokenRequest) -> dict:
    reclamaciones = decode_token(datos.refreshToken)
    if reclamaciones.get("token_type") != "refresh":
        raise ValueError("Token de refresco invalido")
    if normalizar_correo(reclamaciones.get("email", "")) == CORREO_ADMINISTRADOR:
        return respuesta_usuario(usuario_administrador())
    return respuesta_usuario(usuario_actual(correo=reclamaciones.get("email")))


def recuperar_contrasena(datos: PasswordRecoveryRequest) -> dict:
    correo = normalizar_correo(datos.email)
    if correo == CORREO_ADMINISTRADOR:
        raise ValueError("La contraseña del administrador fijo no se puede recuperar desde esta pantalla")
    with sesion_transaccional() as sesion:
        usuario = buscar_por_correo(sesion, correo)
        if not usuario:
            raise ValueError("No existe una cuenta registrada con ese correo")
        usuario.contrasena_hash = contrasena_hash(datos.newPassword.strip())
    return {"message": "Contraseña actualizada", "email": correo}
