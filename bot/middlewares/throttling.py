import time
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)

_user_last_request: dict[int, float] = {}
COMMAND_RATE_LIMIT = 0.5
MESSAGE_RATE_LIMIT = 0.1


class ThrottlingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id if event.from_user else 0
        now = time.monotonic()

        is_command = event.text and event.text.startswith("/")
        limit = COMMAND_RATE_LIMIT if is_command else MESSAGE_RATE_LIMIT

        last = _user_last_request.get(user_id, 0)
        if now - last < limit:
            if is_command:
                await event.answer("\u23f3 \u0421\u043b\u0438\u0448\u043a\u043e\u043c \u0447\u0430\u0441\u0442\u043e. \u041f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435 \u0441\u0435\u043a\u0443\u043d\u0434\u0443.")
            return

        _user_last_request[user_id] = now
        return await handler(event, data)
