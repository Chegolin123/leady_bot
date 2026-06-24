import uuid
from datetime import datetime
from pydantic import BaseModel


class BotCreate(BaseModel):
    company_id: uuid.UUID
    token: str


class BotResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    bot_username: str | None
    bot_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BotListResponse(BaseModel):
    bots: list[BotResponse]
    total: int
