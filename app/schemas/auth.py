from pydantic import BaseModel, Field


class UsuarioRegistro(BaseModel):
    name: str = Field(min_length=2)
    phone: str = Field(min_length=4)
    email: str = Field(min_length=5)
    password: str = Field(min_length=4)
    role: str = "user"


class UsuarioLogin(BaseModel):
    email: str = Field(min_length=5)
    password: str = Field(min_length=1)


class PasswordRecoveryRequest(BaseModel):
    email: str = Field(min_length=5)
    newPassword: str = Field(min_length=4)


class AuthResponse(BaseModel):
    id: int
    email: str
    name: str
    phone: str | None = None
    role: str
    token: str | None = None
