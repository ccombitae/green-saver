from pydantic import BaseModel, Field


class CalculoCrear(BaseModel):
    email: str = Field(min_length=5)
    consumption: float = Field(ge=0)
    estimatedPanels: int = Field(ge=0)
    coverage: float = Field(ge=0)
    estimatedSavings: float = Field(ge=0)
    recommendation: str = ""
    cityId: str | None = Field(default=None, max_length=60)
    estimationId: str | None = Field(default=None, pattern=r"^[0-9a-f]{24}$")


class CalculoResponse(BaseModel):
    id: int
    email: str | None
    consumption: float
    estimatedPanels: int
    coverage: float
    estimatedSavings: float
    recommendation: str
    created_at: str
    cityId: str | None = None
    estimationId: str | None = None
