import uuid
from datetime import datetime
from pydantic import BaseModel


class CompanyCreate(BaseModel):
    name: str
    tariff: str = "base"


class CompanyResponse(BaseModel):
    id: uuid.UUID
    name: str
    tariff: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    companies: list[CompanyResponse]
    total: int
