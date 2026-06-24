import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.schemas.deal import (
    DealCreate, DealUpdate, DealResponse, DealListResponse, DealLogResponse,
)
from core.models.deal import Deal, DealLog

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=DealResponse, status_code=201)
async def create_deal(
    data: DealCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deal = Deal(
        company_id=user.company_id,
        title=data.title,
        amount=data.amount,
        status=data.status,
        client_id=data.client_id,
        responsible_id=user.id,
    )
    db.add(deal)
    await db.commit()
    await db.refresh(deal)

    # Лог создания
    log = DealLog(
        deal_id=deal.id,
        user_id=user.id,
        field_name="status",
        new_value=deal.status,
    )
    db.add(log)
    await db.commit()

    logger.info(f"Deal created: {deal.id} by user {user.id}")
    return deal


@router.get("", response_model=DealListResponse)
async def list_deals(
    status: str | None = Query(None),
    trash: bool = Query(False),
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Deal).where(Deal.company_id == user.company_id)

    if trash:
        query = query.where(Deal.deleted_at.isnot(None))
    else:
        query = query.where(Deal.deleted_at.is_(None))

    if status:
        query = query.where(Deal.status == status)

    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    result = await db.execute(
        query.order_by(Deal.created_at.desc()).offset(offset).limit(limit)
    )
    deals = result.scalars().all()

    return DealListResponse(
        deals=[DealResponse.model_validate(d) for d in deals],
        total=total,
    )


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Deal).where(
            Deal.id == deal_id,
            Deal.company_id == user.company_id,
            Deal.deleted_at.is_(None),
        )
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal


@router.patch("/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: uuid.UUID,
    data: DealUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Deal).where(
            Deal.id == deal_id,
            Deal.company_id == user.company_id,
            Deal.deleted_at.is_(None),
        )
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        old_value = str(getattr(deal, field))
        setattr(deal, field, value)
        if old_value != str(value):
            log = DealLog(
                deal_id=deal.id,
                user_id=user.id,
                field_name=field,
                old_value=old_value,
                new_value=str(value),
            )
            db.add(log)

    await db.commit()
    await db.refresh(deal)
    return deal


@router.delete("/{deal_id}", status_code=204)
async def soft_delete_deal(
    deal_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Deal).where(Deal.id == deal_id, Deal.company_id == user.company_id)
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    deal.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info(f"Deal soft-deleted: {deal_id}")


@router.post("/{deal_id}/restore", response_model=DealResponse)
async def restore_deal(
    deal_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Deal).where(
            Deal.id == deal_id,
            Deal.company_id == user.company_id,
            Deal.deleted_at.isnot(None),
        )
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found in trash")

    deal.deleted_at = None
    await db.commit()
    await db.refresh(deal)
    logger.info(f"Deal restored: {deal_id}")
    return deal


@router.get("/{deal_id}/logs", response_model=list[DealLogResponse])
async def get_deal_logs(
    deal_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DealLog)
        .where(DealLog.deal_id == deal_id)
        .order_by(DealLog.created_at.desc())
        .limit(50)
    )
    logs = result.scalars().all()
    return logs
