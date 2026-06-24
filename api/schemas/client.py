import uuid
from datetime import datetime
from pydantic import BaseModel


class ClientCreate(BaseModel):
    name: str = "Гость"
    telegram_id: int | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class ClientUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    is_lead: bool | None = None


class ClientResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    telegram_id: int | None
    name: str
    phone: str | None
    email: str | None
    notes: str | None
    is_lead: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClientListResponse(BaseModel):
    clients: list[ClientResponse]
    total: int
