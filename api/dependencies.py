import logging
from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.database import get_db
from core.config import settings
from core.models.user import User

logger = logging.getLogger(__name__)


async def get_redis() -> Redis:
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.close()


async def get_current_user(
    x_telegram_id: int = Header(..., alias="X-Telegram-ID"),
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Аутентификация по telegram_id + tenant_id."""
    result = await db.execute(
        select(User).where(
            User.telegram_id == x_telegram_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if x_tenant_id and str(user.company_id) != x_tenant_id:
        raise HTTPException(status_code=403, detail="User does not belong to this company")

    return user


async def require_feature(feature: str, tariff: str):
    """Проверяет доступность фичи по тарифу."""
    from core.feature_flags import get_tariff_features

    available = get_tariff_features(tariff)
    if feature not in available:
        raise HTTPException(
            status_code=403,
            detail=f"Feature '{feature}' is not available on tariff '{tariff}'",
        )
