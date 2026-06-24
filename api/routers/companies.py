import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.schemas.company import CompanyCreate, CompanyResponse, CompanyListResponse
from core.models.company import Company
from core.models.user import User
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(
    data: CompanyCreate,
    x_telegram_id: int | None = Header(None, alias="X-Telegram-ID"),
    db: AsyncSession = Depends(get_db),
):
    import logging as _log

    # Check for duplicate company name
    result = await db.execute(select(Company).where(func.lower(Company.name) == data.name.lower(), Company.deleted_at.is_(None)))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Company with this name already exists")

    _log.getLogger(__name__).info(f"create_company: name={data.name}, tg={x_telegram_id}")
    company = Company(name=data.name, tariff=data.tariff)
    db.add(company)
    await db.flush()

    if x_telegram_id:
        from sqlalchemy import select as _select
        result = await db.execute(
            _select(User).where(User.telegram_id == x_telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.company_id = company.id
            user.role = "owner"
            _log.getLogger(__name__).info(f"Linked user {user.telegram_id} to company {company.id}")

    await db.commit()
    await db.refresh(company)
    _log.getLogger(__name__).info(f"Company created: {company.id} ({company.name})")
    return company


@router.get("", response_model=CompanyListResponse)
async def list_companies(
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

    return CompanyListResponse(
        companies=[CompanyResponse.model_validate(c) for c in companies],
        total=total,
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
