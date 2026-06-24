import hashlib
import hmac
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from core.models.user import User
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/telegram")
async def telegram_auth(
    id: int = Query(...),
    first_name: str = Query(...),
    last_name: str = Query(None),
    username: str = Query(None),
    photo_url: str = Query(None),
    auth_date: int = Query(...),
    hash: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Проверка Telegram Login Widget.
    Валидирует hash и auth_date, возвращает JWT-токен.
    """
    # Проверка auth_date: не старше 24 часов
    if int(time.time()) - auth_date > 86400:
        raise HTTPException(status_code=400, detail="Auth date expired")

    # Проверка hash подписи
    bot_token = settings.BOT_TOKEN
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted([
            ("auth_date", str(auth_date)),
            ("first_name", first_name),
            ("id", str(id)),
            ("last_name", last_name or ""),
            ("photo_url", photo_url or ""),
            ("username", username or ""),
        ]) if v
    )

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if computed_hash != hash:
        logger.warning(f"Invalid Telegram auth hash for user {id}")
        raise HTTPException(status_code=403, detail="Invalid auth hash")

    # Находим или создаем пользователя
    result = await db.execute(
        select(User).where(User.telegram_id == id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not registered. Use /start in bot.")

    # Генерируем простой JWT
    from datetime import datetime, timedelta, timezone
    from jose import jwt

    payload = {
        "sub": str(user.id),
        "telegram_id": user.telegram_id,
        "company_id": str(user.company_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    token = jwt.encode(payload, settings.SERVICE_API_TOKEN, algorithm="HS256")

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "telegram_id": user.telegram_id,
            "first_name": user.first_name,
            "username": user.username,
            "company_id": str(user.company_id),
        },
    }
