import asyncio
from typing import Optional

from bot.dto import ActorDTO

_lock = asyncio.Lock()
_store: dict[int, ActorDTO] = {}


async def set_auth(telegram_id: int, actor: ActorDTO) -> None:
    async with _lock:
        _store[telegram_id] = actor


def get_auth(telegram_id: int) -> Optional[ActorDTO]:
    return _store.get(telegram_id)


async def evict_auth(telegram_id: int) -> None:
    async with _lock:
        _store.pop(telegram_id, None)
