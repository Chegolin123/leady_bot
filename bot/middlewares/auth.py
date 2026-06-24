import json
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from redis.asyncio import Redis

from bot.api_client import api
from bot.auth_store import set_auth
from bot.dto import ActorDTO
from core.config import settings

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis):
        self.redis = redis
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None:
            data["auth"] = None
            return await handler(event, data)

        telegram_id = tg_user.id
        cache_key = f"user:{telegram_id}"

        cached = await self._cache_get(cache_key)
        if cached is not None:
            data["auth"] = cached
            await set_auth(telegram_id, cached)
            return await handler(event, data)

        try:
            actor_raw = await api.get_or_create_actor(
                telegram_id=telegram_id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )
        except Exception:
            logger.exception(f"Failed to resolve actor {telegram_id}")
            actor = self._anonymous(tg_user)
            data["auth"] = actor
            await set_auth(telegram_id, actor)
            return await handler(event, data)

        api_role = actor_raw.get("role", "")
        is_admin = (api_role == "admin") or (
            not api_role and telegram_id in settings.admin_ids
        )

        actor = ActorDTO(
            actor_id=actor_raw.get("id", ""),
            telegram_id=telegram_id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            is_admin=is_admin,
            pd_consent=actor_raw.get("pd_consent", False),
            role=api_role or "guest",
            company_id=actor_raw.get("company_id"),
            company_name=actor_raw.get("company_name", ""),
            tariff=actor_raw.get("tariff", "base"),
        )
        data["auth"] = actor
        await self._cache_set(cache_key, actor)
        await set_auth(telegram_id, actor)
        return await handler(event, data)

    async def _cache_get(self, key: str) -> ActorDTO | None:
        try:
            raw = await self.redis.get(key)
            if raw is None:
                return None
            obj = json.loads(raw)
            return ActorDTO(**obj)
        except Exception:
            return None

    async def _cache_set(self, key: str, actor: ActorDTO) -> None:
        try:
            payload = {
                "actor_id": actor.actor_id,
                "telegram_id": actor.telegram_id,
                "username": actor.username,
                "first_name": actor.first_name,
                "last_name": actor.last_name,
                "is_admin": actor.is_admin,
                "pd_consent": actor.pd_consent,
                "role": actor.role,
                "company_id": actor.company_id,
                "company_name": actor.company_name,
                "tariff": actor.tariff,
            }
            await self.redis.setex(key, settings.USER_CACHE_TTL, json.dumps(payload))
        except Exception:
            pass

    def _anonymous(self, tg_user: TgUser) -> ActorDTO:
        return ActorDTO(
            actor_id="",
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            is_admin=tg_user.id in settings.admin_ids,
            pd_consent=False,
        )
