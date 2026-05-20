from pydantic import BaseModel, Field


class SystemPayload(BaseModel):
    capacity: str = ""
    panels: str = ""
    inverter: str = ""
    battery: str = ""
    installDate: str = ""


class SystemAssignRequest(BaseModel):
    email: str = Field(min_length=5)
    system: SystemPayload