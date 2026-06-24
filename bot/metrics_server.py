import asyncio
import logging

from aiohttp import web
from prometheus_client import generate_latest

from core.config import settings

logger = logging.getLogger(__name__)


async def metrics_handler(request: web.Request) -> web.Response:
    return web.Response(body=generate_latest(), content_type="text/plain")


async def health_handler(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def start_metrics_server() -> None:
    app = web.Application()
    app.router.add_get("/metrics", metrics_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.METRICS_PORT)

    logger.info(f"Metrics server on :{settings.METRICS_PORT}")
    await site.start()

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("Metrics server stopping")
        await runner.cleanup()
