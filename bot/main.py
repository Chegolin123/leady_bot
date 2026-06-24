import asyncio
import logging
import signal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from bot.handlers import (
    start, admin, legal, nav, debug
)
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.errors import ErrorMetricsMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.services.heartbeat import heartbeat_loop
from bot.metrics_server import start_metrics_server
from core.config import settings
from core.proxy_manager import DynamicProxySession
from core.logging_config import setup_logging

logger = logging.getLogger(__name__)

_running_tasks: list[asyncio.Task] = []
_metrics_task: asyncio.Task | None = None


async def healthcheck_loop(proxy: DynamicProxySession, interval: int = 30) -> None:
    while True:
        await asyncio.sleep(interval)
        ok = await proxy.healthcheck()
        if not ok:
            logger.warning("Proxy healthcheck failed, rotating...")
            await proxy.rotate()


async def shutdown(
    sig: signal.Signals,
    bot: Bot,
    dp: Dispatcher,
    redis: Redis,
    proxy: DynamicProxySession | None,
) -> None:
    logger.info(f"Received signal {sig.name}, shutting down...")

    for task in _running_tasks:
        task.cancel()

    if _metrics_task:
        _metrics_task.cancel()

    try:
        await dp.stop_polling()
    except Exception:
        logger.exception("Error stopping dispatcher")

    try:
        await redis.close()
    except Exception:
        logger.exception("Error closing Redis")

    try:
        await bot.session.close()
    except Exception:
        logger.exception("Error closing bot session")

    if proxy:
        try:
            await proxy.close()
        except Exception:
            logger.exception("Error closing proxy")

    logger.info("Shutdown complete.")


async def main() -> None:
    setup_logging()
    logger.info("Starting LeadyCRM bot...")

    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    proxy: DynamicProxySession | None = None
    if settings.proxy_urls:
        proxy = DynamicProxySession(settings.proxy_urls)
        try:
            session = await proxy.get_session()
            bot = Bot(
                token=settings.BOT_TOKEN,
                session=session,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
            me = await bot.get_me()
            logger.info(f"Bot @{me.username} via proxy")
        except Exception as e:
            logger.warning(f"Proxy failed ({e}), fallback to direct connection")
            bot = Bot(
                token=settings.BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
            me = await bot.get_me()
            logger.info(f"Bot @{me.username} via direct")
    else:
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        me = await bot.get_me()
        logger.info(f"Bot @{me.username} via direct")

    storage = RedisStorage(redis)
    dp = Dispatcher(storage=storage)

    dp.update.middleware(ErrorMetricsMiddleware())
    dp.update.middleware(AuthMiddleware(redis))
    dp.message.middleware(ThrottlingMiddleware())

    dp.include_router(nav.router)
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(legal.router)
    dp.include_router(debug.router)

    # ── Фоновые задачи ──
    _running_tasks.append(asyncio.create_task(heartbeat_loop(redis)))
    if proxy is not None:
        _running_tasks.append(asyncio.create_task(healthcheck_loop(proxy)))

    global _metrics_task
    _metrics_task = asyncio.create_task(start_metrics_server())

    # ── Graceful shutdown ──
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s, bot, dp, redis, proxy)),
        )

    logger.info("Bot polling started")
    try:
        await dp.start_polling(bot)
    finally:
        for task in _running_tasks:
            task.cancel()
        if _metrics_task:
            _metrics_task.cancel()
        if proxy:
            await proxy.close()
        await redis.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
