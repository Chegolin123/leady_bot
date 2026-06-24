import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from core.models.client import Client
from core.models.deal import Deal

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/export")
async def export_pd(
    client_id: str = Query(None, description="UUID клиента для экспорта"),
    search: str = Query(None, description="Поиск клиента по имени/телефону"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Экспорт персональных данных клиента (152-ФЗ, для РКН)."""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant not found")

    if client_id:
        query = select(Client).where(
            Client.id == client_id,
            Client.company_id == tenant_id,
        )
        result = await db.execute(query)
        client = result.scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        clients = [client]
    elif search:
        query = select(Client).where(
            Client.company_id == tenant_id,
            (Client.name.ilike(f"%{search}%")) | (Client.phone.ilike(f"%{search}%")),
        )
        result = await db.execute(query)
        clients = result.scalars().all()
    else:
        raise HTTPException(status_code=400, detail="Provide client_id or search query")

    export_data = []
    for c in clients:
        deals_query = select(Deal).where(
            Deal.client_id == c.id,
            Deal.company_id == tenant_id,
        )
        deals_result = await db.execute(deals_query)
        deals = deals_result.scalars().all()

        export_data.append({
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "operator": {
                "name": "Чеголин Алексей Михайлович",
                "inn": "502714865303",
                "status": "Самозанятый (НПД)",
            },
            "subject": {
                "name": c.name,
                "phone": c.phone,
                "email": c.email,
                "telegram_id": c.telegram_id,
                "notes": c.notes,
            },
            "processing_purpose": "CRM-система для управления продажами (152-ФЗ ст.9)",
            "legal_basis": "Согласие субъекта ПД (152-ФЗ ст.9)",
            "data_source": "Входящее сообщение Telegram",
            "interactions": [
                {
                    "deal_id": str(d.id),
                    "title": d.title,
                    "amount": str(d.amount) if d.amount else None,
                    "status": d.status,
                }
                for d in deals
            ],
            "retention_period": "До отзыва согласия + 90 дней (152-ФЗ ст.9 ч.4)",
        })

    return JSONResponse(content={"count": len(export_data), "data": export_data})
