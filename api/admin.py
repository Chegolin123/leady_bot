import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from core.models.company import Company
from core.models.license import License
from core.models.user import User
from core.models.deal import Deal
from core.models.client import Client

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="api/templates/admin")
router = APIRouter()


@router.get("", response_class=HTMLResponse)
async def admin_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/companies", response_class=HTMLResponse)
async def admin_companies(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    total_q = select(func.count(Company.id)).where(Company.deleted_at.is_(None))
    total = (await db.execute(total_q)).scalar() or 0

    result = await db.execute(
        select(Company)
        .where(Company.deleted_at.is_(None))
        .order_by(Company.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    companies = result.scalars().all()

    company_data = []
    for c in companies:
        lic_result = await db.execute(
            select(License).where(
                License.company_id == c.id,
                License.is_active == True,
            ).order_by(License.expires_at.desc()).limit(1)
        )
        active_license = lic_result.scalar_one_or_none()

        user_count = (await db.execute(
            select(func.count(User.id)).where(
                User.company_id == c.id,
                User.deleted_at.is_(None),
            )
        )).scalar() or 0

        company_data.append({
            "id": c.id,
            "name": c.name,
            "tariff": c.tariff,
            "created_at": c.created_at,
            "active_license": active_license,
            "managers_count": user_count,
        })

    return templates.TemplateResponse("companies.html", {
        "request": request,
        "companies": company_data,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get("/companies/{company_id}", response_class=HTMLResponse)
async def admin_company_detail(
    request: Request,
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    licenses = (await db.execute(
        select(License).where(License.company_id == company_id).order_by(License.created_at.desc()).limit(20)
    )).scalars().all()

    users = (await db.execute(
        select(User).where(User.company_id == company_id, User.deleted_at.is_(None))
    )).scalars().all()

    deals_count = (await db.execute(
        select(func.count(Deal.id)).where(
            Deal.company_id == company_id,
            Deal.deleted_at.is_(None),
        )
    )).scalar() or 0

    clients_count = (await db.execute(
        select(func.count(Client.id)).where(
            Client.company_id == company_id,
            Client.deleted_at.is_(None),
        )
    )).scalar() or 0

    return templates.TemplateResponse("company_detail.html", {
        "request": request,
        "company": company,
        "licenses": licenses,
        "users": users,
        "deals_count": deals_count,
        "clients_count": clients_count,
    })


@router.post("/companies/{company_id}/activate")
async def admin_activate_license(
    company_id: uuid.UUID,
    tariff: str = Query("base"),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timedelta, timezone

    license_obj = License(
        company_id=company_id,
        tariff=tariff,
        is_active=True,
        amount=0,
        payment_id="manual",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(license_obj)
    await db.commit()

    # Инвалидируем кеш
    from redis.asyncio import Redis
    from core.config import settings
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis.delete(f"license:{company_id}")
    await redis.close()

    logger.info(f"License manually activated for company {company_id}")
    return {"status": "ok"}


@router.post("/companies/{company_id}/deactivate")
async def admin_deactivate_license(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(License).where(
            License.company_id == company_id,
            License.is_active == True,
        )
    )
    for lic in result.scalars().all():
        lic.is_active = False

    await db.commit()

    from redis.asyncio import Redis
    from core.config import settings
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis.delete(f"license:{company_id}")
    await redis.close()

    logger.info(f"License manually deactivated for company {company_id}")
    return {"status": "ok"}
