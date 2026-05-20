from pydantic import BaseModel, Field


class MaterialSelection(BaseModel):
    panelType: str
    inverterType: str
    batteryType: str
    structureType: str


class QuoteSendRequest(BaseModel):
    calculationId: int
    clientEmail: str = Field(min_length=5)
    clientName: str = "Cliente"
    totalPrice: float
    notes: str = ""
    materials: MaterialSelection


class QuoteSendResponse(BaseModel):
    id: int
    calculationId: int
    clientEmail: str
    status: str
    sentAt: str


class QuoteAcceptRequest(BaseModel):
    installDate: str = Field(min_length=1)


class QuoteAcceptResponse(BaseModel):
    quoteId: int
    status: str
    installDate: str
