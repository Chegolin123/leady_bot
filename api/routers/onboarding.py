from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from core.models.user import User

router = APIRouter(prefix="/api/onboarding")

CONSENT_TEXT = """Пользовательское соглашение и политика обработки персональных данных Leady CRM.

1. ОБЩИЕ ПОЛОЖЕНИЯ
1.1. Настоящее соглашение регулирует отношения между Leady CRM (далее — «Платформа») и пользователем.
1.2. Используя бота @LEADYCRM_bot, вы подтверждаете согласие с условиями.

2. ПЕРСОНАЛЬНЫЕ ДАННЫЕ
2.1. Платформа обрабатывает: Telegram ID, имя пользователя, username, название компании.
2.2. Данные используются для предоставления CRM-услуг и поддержки.
2.3. Платформа не передаёт данные третьим лицам.

3. ПРАВА ПОЛЬЗОВАТЕЛЯ
3.1. Вы можете отозвать согласие через /revoke_consent.
3.2. Вы можете запросить удаление аккаунта через /delete_account.

4. СРОК ДЕЙСТВИЯ
4.1. Согласие действует с момента принятия до отзыва."""


@router.get("/consent")
async def get_consent():
    return {
        "text": CONSENT_TEXT,
        "version": "1.0",
    }


@router.post("/accept-consent")
async def accept_consent(data: dict, db: AsyncSession = Depends(get_db)):
    telegram_id = data.get("telegram_id") if data else None
    if not telegram_id:
        raise HTTPException(status_code=400, detail="telegram_id required")

    result = await db.execute(
        select(User).where(
            User.telegram_id == telegram_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.pd_consent = True
    user.pd_consent_at = datetime.now(timezone.utc)
    await db.commit()

    return {"ok": True, "pd_consent": True}
