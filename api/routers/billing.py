import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yookassa import Configuration, Payment

from api.dependencies import get_db
from api.schemas.billing import PaymentCreate, PaymentResponse, WebhookPayload
from core.models.license import License
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET


def _calculate_tariff_days(tariff: str) -> int:
    return 30  # месяц


@router.post("/pay", response_model=PaymentResponse)
async def create_payment(
    data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        payment = Payment.create({
            "amount": {
                "value": str(data.amount),
                "currency": "RUB",
            },
            "confirmation": {
                "type": "redirect",
                "return_url": data.return_url or "https://leadycrm.ru",
            },
            "capture": True,
            "description": f"CRM-бот: тариф {data.tariff.title()}",
            "metadata": {
                "company_id": str(data.company_id),
                "tariff": data.tariff,
            },
        }, idempotency_key=str(uuid.uuid4()))

        return PaymentResponse(
            payment_id=payment.id,
            confirmation_url=payment.confirmation.confirmation_url,
            amount=data.amount,
            status=payment.status,
        )

    except Exception as e:
        logger.error(f"YooKassa payment creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Payment error: {str(e)}")


@router.post("/webhook")
async def billing_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()

    # Проверка HMAC-подписи (если настроена в YooKassa)
    signature = request.headers.get("X-YooKassa-Signature")
    if signature:
        expected = hmac.new(
            settings.YOOKASSA_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("YooKassa webhook: invalid HMAC signature")
            raise HTTPException(status_code=403, detail="Invalid signature")

    import json
    payload = json.loads(body)
    event = payload.get("event", "")
    obj = payload.get("object", {})

    if event == "payment.succeeded":
        metadata = obj.get("metadata", {})
        company_id = metadata.get("company_id")
        tariff = metadata.get("tariff", "base")
        payment_id = obj.get("id")
        amount = float(obj.get("amount", {}).get("value", 0))

        if company_id:
            # Деактивируем старые лицензии
            old_licenses = await db.execute(
                select(License).where(
                    License.company_id == uuid.UUID(company_id),
                    License.is_active == True,
                )
            )
            for lic in old_licenses.scalars().all():
                lic.is_active = False

            # Создаем новую лицензию
            days = _calculate_tariff_days(tariff)
            license_obj = License(
                company_id=uuid.UUID(company_id),
                tariff=tariff,
                is_active=True,
                payment_id=payment_id,
                amount=amount,
                expires_at=datetime.now(timezone.utc) + timedelta(days=days),
            )
            db.add(license_obj)
            await db.commit()

            logger.info(
                f"License activated: company={company_id}, "
                f"tariff={tariff}, expires={license_obj.expires_at}"
            )

    return {"status": "ok"}
