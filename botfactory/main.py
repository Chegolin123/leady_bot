"""Bot Factory — Telethon-based bot creation via @BotFather.

POST /create-bot  {"name": "...", "username": "..."}  →  {"token": "...", "ok": true}
GET /health
"""

import asyncio
import logging
import os
import sys

from aiohttp import web
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, SessionPasswordNeededError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("botfactory")

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE = os.getenv("TELEGRAM_PHONE", "")
SESSION_FILE = os.getenv("SESSION_FILE", "/data/botfactory.session")

_client: TelegramClient | None = None


async def get_client() -> TelegramClient:
    global _client
    if _client is not None and _client.is_connected():
        return _client

    _client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await _client.start(phone=PHONE)
    logger.info("Telethon client connected")
    return _client


async def create_bot_via_botfather(name: str, username: str) -> dict:
    client = await get_client()

    try:
        botfather = await client.get_input_entity("BotFather")
    except Exception as e:
        return {"ok": False, "error": f"Cannot resolve BotFather: {e}"}

    try:
        await client.send_message(botfather, "/newbot")
    except FloodWaitError as e:
        return {"ok": False, "error": f"Flood wait {e.seconds}s"}

    await asyncio.sleep(1)

    await client.send_message(botfather, name)
    await asyncio.sleep(1)

    async for msg in client.iter_messages(botfather, limit=1):
        if "Sorry" in (msg.text or ""):
            return {"ok": False, "error": "Name rejected by BotFather"}
        if "username" not in (msg.text or "").lower():
            await asyncio.sleep(1)

    await client.send_message(botfather, username)
    await asyncio.sleep(2)

    token = None
    async for msg in client.iter_messages(botfather, limit=5):
        text = msg.text or ""
        if "Done!" in text or "token" in text.lower():
            import re
            match = re.search(r"(\d{8,10}:[\w-]{35})", text)
            if match:
                token = match.group(1)
                break

    if token:
        return {"ok": True, "token": token}
    return {"ok": False, "error": "Token not found in BotFather response"}


async def handle_create(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

    name = (body.get("name") or "").strip()
    username = (body.get("username") or "").strip().lower()

    if not name or not username:
        return web.json_response({"ok": False, "error": "name and username required"}, status=400)

    logger.info(f"Creating bot: {name} (@{username})")
    result = await create_bot_via_botfather(name, username)
    return web.json_response(result)


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def main():
    port = int(os.getenv("PORT", "9000"))
    app = web.Application()
    app.router.add_post("/create-bot", handle_create)
    app.router.add_get("/health", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Bot factory on :{port}")

    try:
        await get_client()
    except Exception as e:
        logger.warning(f"Telethon not connected yet: {e}")
        logger.info("Send POST /create-bot to trigger login flow")

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
