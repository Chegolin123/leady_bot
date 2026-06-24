import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class PaymentCreate(BaseModel):
    company_id: uuid.UUID
    tariff: str
    amount: Decimal
    return_url: str | None = None


class PaymentResponse(BaseModel):
    payment_id: str
    confirmation_url: str
    amount: Decimal
    status: str


class WebhookPayload(BaseModel):
    event: str
    object: dict


class LicenseInfo(BaseModel):
    company_id: uuid.UUID
    tariff: str
    is_active: bool
    expires_at: datetime

    model_config = {"from_attributes": True}


class LicenseCheckResponse(BaseModel):
    active: bool
    tariff: str | None
    expires_at: datetime | None
    message: str | None
