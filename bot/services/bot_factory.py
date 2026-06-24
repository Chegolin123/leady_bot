"""HTTP client for bot-factory service."""

import logging

import httpx

logger = logging.getLogger(__name__)

FACTORY_URL = "http://botfactory:9000"


async def create_bot(name: str, username: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{FACTORY_URL}/create-bot",
                json={"name": name, "username": username},
            )
            return resp.json()
    except Exception as e:
        logger.error(f"Bot factory error: {e}")
        return {"ok": False, "error": str(e)}
