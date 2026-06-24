import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from core.models.deal import Deal

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/analytics/funnel")
async def funnel(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Воронка продаж: количество сделок по статусам."""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant not found")

    query = (
        select(Deal.status, func.count(Deal.id).label("count"))
        .where(Deal.company_id == tenant_id, Deal.deleted_at.is_(None))
        .group_by(Deal.status)
    )
    result = await db.execute(query)
    rows = result.all()

    funnel_order = ["new", "in_progress", "negotiation", "invoice_sent", "won", "lost"]
    status_map = {
        "new": "Новый",
        "in_progress": "В работе",
        "negotiation": "Переговоры",
        "invoice_sent": "Счёт выставлен",
        "won": "Выиграл",
        "lost": "Проиграл",
    }

    data = {}
    for status in funnel_order:
        data[status] = {"label": status_map.get(status, status), "count": 0}
    for row in rows:
        data[row.status]["count"] = row.count

    return {"funnel": [{"status": k, **v} for k, v in data.items()]}


@router.get("/analytics/summary")
async def summary(
    period_days: int = Query(30, description="Период в днях (по умолчанию 30)"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Сводка: всего сделок, выиграно, конверсия, выручка."""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant not found")

    since = datetime.utcnow() - timedelta(days=period_days)

    query = (
        select(
            func.count(Deal.id).label("total"),
            func.sum(case((Deal.status == "won", 1), else_=0)).label("won"),
            func.sum(case((Deal.status == "lost", 1), else_=0)).label("lost"),
            func.coalesce(func.sum(Deal.amount), 0).label("total_amount"),
            func.coalesce(
                func.sum(case((Deal.status == "won", Deal.amount), else_=0)), 0
            ).label("won_amount"),
        )
        .where(
            Deal.company_id == tenant_id,
            Deal.deleted_at.is_(None),
            Deal.created_at >= since,
        )
    )
    result = await db.execute(query)
    row = result.one()

    total = row.total or 0
    won = row.won or 0
    lost = row.lost or 0
    active = total - won - lost

    return {
        "period_days": period_days,
        "total_deals": total,
        "active_deals": active,
        "won_deals": won,
        "lost_deals": lost,
        "conversion_rate": round(won / total * 100, 1) if total > 0 else 0,
        "total_amount": float(row.total_amount),
        "won_amount": float(row.won_amount),
    }


@router.get("/analytics/monthly")
async def monthly(
    months: int = Query(6, description="Количество месяцев"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Динамика по месяцам: сделки, выручка."""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant not found")

    since = datetime.utcnow() - timedelta(days=months * 31)

    query = (
        select(
            func.date_trunc("month", Deal.created_at).label("month"),
            func.count(Deal.id).label("count"),
            func.coalesce(func.sum(Deal.amount), 0).label("amount"),
        )
        .where(
            Deal.company_id == tenant_id,
            Deal.deleted_at.is_(None),
            Deal.created_at >= since,
        )
        .group_by(func.date_trunc("month", Deal.created_at))
        .order_by("month")
    )
    result = await db.execute(query)
    rows = result.all()

    return {
        "months": [
            {
                "month": row.month.strftime("%Y-%m"),
                "deals": row.count,
                "amount": float(row.amount),
            }
            for row in rows
        ]
    }
