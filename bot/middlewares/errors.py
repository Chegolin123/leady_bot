import logging
import time
from collections.abc import Callable
from typing import Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

MESSAGES_TOTAL = Counter(
    "leady_messages_total",
    "Total messages processed",
    ["handler", "command"],
)
ERRORS_TOTAL = Counter(
    "leady_errors_total",
    "Total errors",
    ["handler", "error_type"],
)
MESSAGE_DURATION = Histogram(
    "leady_message_duration_seconds",
    "Message processing duration",
    ["handler"],
)


class ErrorMetricsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        handler_name = data.get("handler", {}).__class__.__name__ if data.get("handler") else "unknown"
        is_command = getattr(event, "text", "") and getattr(event, "text", "").startswith("/")
        command_label = "command" if is_command else "message"

        start = time.monotonic()
        try:
            result = await handler(event, data)
            MESSAGES_TOTAL.labels(handler=handler_name, command=command_label).inc()
            return result
        except Exception as exc:
            ERRORS_TOTAL.labels(handler=handler_name, error_type=type(exc).__name__).inc()
            raise
            raise
        finally:
            MESSAGE_DURATION.labels(handler=handler_name).observe(time.monotonic() - start)
