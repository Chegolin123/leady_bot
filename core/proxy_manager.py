import asyncio
import logging
import random

from aiogram.client.session.aiohttp import AiohttpSession

logger = logging.getLogger(__name__)


class DynamicProxySession:
    def __init__(self, proxy_urls: list[str]):
        if not proxy_urls:
            raise ValueError("At least one proxy URL is required")
        self._urls = list(proxy_urls)
        self._index: int = 0
        self._session: AiohttpSession | None = None
        self._lock = asyncio.Lock()

    async def get_session(self) -> AiohttpSession:
        async with self._lock:
            if self._session is not None:
                return self._session
            await self._rotate()
            return self._session

    async def healthcheck(self) -> bool:
        async with self._lock:
            if self._session is None:
                return False
            url = self._urls[self._index % len(self._urls)]
            logger.debug(f"Proxy healthcheck: {url}")
            return True

    async def rotate(self) -> None:
        async with self._lock:
            await self._rotate()

    async def _rotate(self) -> None:
        if self._session is not None:
            await self._session.close()
        self._index = (self._index + 1) % len(self._urls)
        url = self._urls[self._index]
        logger.info(f"Rotating proxy to [{self._index}] {url}")
        self._session = AiohttpSession(proxy=url)

    async def close(self) -> None:
        async with self._lock:
            if self._session is not None:
                await self._session.close()
                self._session = None
