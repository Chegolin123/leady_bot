import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.dependencies import get_db
from core.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/actor")


@router.get("/{telegram_id}")
async def get_or_create_actor(
    telegram_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .options(selectinload(User.company))
        .where(
            User.telegram_id == telegram_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(telegram_id=telegram_id, role="owner")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    company_id = str(user.company_id) if user.company_id else None
    company_name = user.company.name if user.company else ""

    return {
        "id": str(user.id),
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "company_id": company_id,
        "company_name": company_name,
        "tariff": user.company.tariff if user.company else "base",
        "pd_consent": user.pd_consent or False,
        "is_active": user.is_active,
    }


@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc()).limit(50)
    )
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "telegram_id": u.telegram_id,
            "username": u.username,
            "first_name": u.first_name,
            "role": u.role,
        }
        for u in users
    ]


@router.get("/users/{user_id}")
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(user.id),
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "company_id": str(user.company_id) if user.company_id else None,
    }
