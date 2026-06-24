import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class DealCreate(BaseModel):
    title: str
    amount: Decimal | None = None
    status: str = "new"
    client_id: uuid.UUID | None = None


class DealUpdate(BaseModel):
    title: str | None = None
    amount: Decimal | None = None
    status: str | None = None
    client_id: uuid.UUID | None = None
    responsible_id: uuid.UUID | None = None


class DealResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    amount: Decimal | None
    status: str
    client_id: uuid.UUID | None
    responsible_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DealListResponse(BaseModel):
    deals: list[DealResponse]
    total: int


class DealLogResponse(BaseModel):
    id: uuid.UUID
    field_name: str
    old_value: str | None
    new_value: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
