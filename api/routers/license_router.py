import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from api.dependencies import get_db, get_redis
from api.schemas.billing import LicenseCheckResponse
from core.models.license import License

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/check/{company_id}", response_model=LicenseCheckResponse)
async def check_license(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    cache_key = f"license:{company_id}"

    # Проверяем Redis-кеш
    cached = await redis.get(cache_key)
    if cached:
        import json
        data = json.loads(cached)
        return LicenseCheckResponse(**data)

    # Ищем активную лицензию в БД
    result = await db.execute(
        select(License).where(
            License.company_id == company_id,
            License.is_active == True,
            License.expires_at > datetime.now(timezone.utc),
        ).order_by(License.expires_at.desc())
    )
    license_obj = result.scalars().first()

    if license_obj:
        response = LicenseCheckResponse(
            active=True,
            tariff=license_obj.tariff,
            expires_at=license_obj.expires_at,
            message=None,
        )
    else:
        response = LicenseCheckResponse(
            active=False,
            tariff=None,
            expires_at=None,
            message="No active license. Please renew.",
        )

    # Кешируем
    import json
    await redis.setex(
        cache_key,
        900,  # 15 минут
        json.dumps(response.model_dump(), default=str),
    )

    return response


@router.post("/invalidate/{company_id}")
async def invalidate_license_cache(
    company_id: uuid.UUID,
    redis: Redis = Depends(get_redis),
):
    cache_key = f"license:{company_id}"
    await redis.delete(cache_key)
    logger.info(f"License cache invalidated for company {company_id}")
    return {"status": "ok", "message": "Cache invalidated"}
