import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.schemas.bot import BotCreate, BotResponse, BotListResponse
from core.models.bot import Bot
from core.encryption import encryption

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=BotResponse, status_code=201)
async def add_bot(
    data: BotCreate,
    db: AsyncSession = Depends(get_db),
):
    # Валидация токена через Telegram API
    token = data.token.strip()
    try:
        from aiogram import Bot as AiogramBot
        from aiogram.client.default import DefaultBotProperties

        test_bot = AiogramBot(
            token=token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        me = await test_bot.get_me()
        await test_bot.session.close()

        encrypted_token = encryption.encrypt(token)

        bot = Bot(
            company_id=data.company_id,
            token_encrypted=encrypted_token,
            bot_username=me.username,
            bot_name=me.first_name,
        )
        db.add(bot)
        await db.commit()
        await db.refresh(bot)

        logger.info(f"Bot added: @{me.username} for company {data.company_id}")
        return bot

    except Exception as e:
        logger.error(f"Bot token validation failed: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid bot token: {str(e)}")


@router.get("", response_model=BotListResponse)
async def list_bots(
    company_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Bot)
    if company_id:
        import uuid
        query = query.where(Bot.company_id == uuid.UUID(company_id))

    from sqlalchemy import func
    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    result = await db.execute(
        query.order_by(Bot.created_at.desc()).offset(offset).limit(limit)
    )
    bots = result.scalars().all()

    return BotListResponse(
        bots=[BotResponse.model_validate(b) for b in bots],
        total=total,
    )
