from pydantic import BaseModel, Field


class CalculoCrear(BaseModel):
    email: str = Field(min_length=5)
    consumption: float
    estimatedPanels: int
    coverage: float
    estimatedSavings: float
    recommendation: str


class CalculoResponse(BaseModel):
    id: int
    email: str
    consumption: float
    estimatedPanels: int
    coverage: float
    estimatedSavings: float
    recommendation: str
    created_at: str
