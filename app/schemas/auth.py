from pydantic import BaseModel, Field


class UsuarioRegistro(BaseModel):
    name: str = Field(min_length=2)
    phone: str = Field(min_length=4)
    email: str = Field(min_length=5)
    password: str = Field(min_length=4, max_length=72)
    role: str = "user"


class UsuarioLogin(BaseModel):
    email: str = Field(min_length=5)
    password: str = Field(min_length=1)


class PasswordRecoveryRequest(BaseModel):
    email: str = Field(min_length=5)
    newPassword: str = Field(min_length=4, max_length=72)


class RefreshTokenRequest(BaseModel):
    refreshToken: str = Field(min_length=20)


class AuthResponse(BaseModel):
    id: int
    email: str
    name: str
    phone: str | None = None
    role: str
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    refresh_expires_in: int | None = None

 