from pydantic import BaseModel, Field


class EstimacionSolicitud(BaseModel):
    consumo_mensual_kwh: float = Field(..., gt=0, le=100000, description="Consumo mensual del hogar en kWh")
    ciudad_id: str = Field(..., min_length=1, max_length=60, description="Id de la ciudad (GET /ml/ciudades)")
    potencia_panel_w: float = Field(550, ge=100, le=800, description="Potencia de cada panel en W")
    rendimiento: float = Field(0.80, gt=0.5, le=0.95, description="Performance ratio del sistema")
    tarifa_kwh_cop: float = Field(850, gt=0, le=5000, description="Tarifa de energía en COP por kWh")
