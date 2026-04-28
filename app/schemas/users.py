from pydantic import BaseModel, Field


class UsuarioCreate(BaseModel):
    nombre: str = Field(min_length=2)
    ciudad: str = "N/A"
    consumo_mensual: float = 0


class UsuarioUpdate(BaseModel):
    nombre: str = Field(min_length=2)
    ciudad: str = "N/A"
    consumo_mensual: float = 0


class UsuarioRead(BaseModel):
    id: int
    nombre: str
    email: str | None = None
    telefono: str | None = None
    rol: str | None = None
    ciudad: str | None = None
    consumo_mensual: float | None = None
