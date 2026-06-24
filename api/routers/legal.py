import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from api.dependencies import get_db
from core.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/legal")


@router.post("/revoke-consent")
async def revoke_consent(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    telegram_id = data.get("telegram_id") if data else None
    if not telegram_id:
        raise HTTPException(status_code=400, detail="telegram_id required")

    result = await db.execute(
        select(User).where(
            User.telegram_id == telegram_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.pd_consent = False
    await db.commit()
    return {"ok": True}


@router.post("/delete-account")
async def delete_account(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    telegram_id = data.get("telegram_id") if data else None
    if not telegram_id:
        raise HTTPException(status_code=400, detail="telegram_id required")

    result = await db.execute(
        select(User).where(
            User.telegram_id == telegram_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, "message": "Account deletion requested"}
