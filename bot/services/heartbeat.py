import asyncio
import logging

from redis.asyncio import Redis

from bot.api_client import api
from core.config import settings

logger = logging.getLogger(__name__)

ACTIVE_COMPANIES_KEY = "active_companies"


async def heartbeat_loop(redis: Redis) -> None:
    while True:
        await asyncio.sleep(settings.HEARTBEAT_INTERVAL_SEC)
        try:
            company_ids = await redis.smembers(ACTIVE_COMPANIES_KEY)
            if not company_ids:
                continue

            for company_id in company_ids:
                try:
                    result = await api.get_company(company_id)
                    cache_key = f"license:{company_id}"
                    await redis.setex(
                        cache_key,
                        settings.LICENSE_CACHE_TTL,
                        str(result.get("active", False)),
                    )
                except Exception:
                    logger.warning(f"Heartbeat failed for company {company_id}")
        except Exception:
            logger.exception("Heartbeat loop error")
