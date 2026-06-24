import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from core.models.bot import Bot
from core.encryption import encryption

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/bots/activate")
async def activate_bot(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Активация бота: принимает токен, валидирует через Telegram API, сохраняет."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    token = body.get("token", "").strip()
    company_id = body.get("company_id", "").strip()

    if not token or not company_id:
        raise HTTPException(status_code=400, detail="token and company_id required")

    # Валидация токена через Telegram API
    try:
        from aiogram import Bot as AiogramBot
        from aiogram.client.default import DefaultBotProperties

        test_bot = AiogramBot(
            token=token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        me = await test_bot.get_me()
        await test_bot.session.close()

    except Exception as e:
        logger.error(f"Bot token validation failed: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid bot token: {str(e)}")

    # Шифруем и сохраняем
    import uuid

    encrypted_token = encryption.encrypt(token)
    bot = Bot(
        company_id=uuid.UUID(company_id),
        token_encrypted=encrypted_token,
        bot_username=me.username,
        bot_name=me.first_name,
    )
    db.add(bot)
    await db.commit()
    await db.refresh(bot)

    logger.info(f"Bot activated: @{me.username} for company {company_id}")

    return {
        "status": "ok",
        "bot_id": str(bot.id),
        "bot_username": me.username,
        "bot_name": me.first_name,
        "message": "Бот успешно активирован. Перейдите в бота и нажмите /start.",
    }
