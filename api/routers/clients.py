import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.schemas.client import ClientCreate, ClientUpdate, ClientResponse, ClientListResponse
from core.models.client import Client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    data: ClientCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    client = Client(
        company_id=user.company_id,
        name=data.name,
        telegram_id=data.telegram_id,
        phone=data.phone,
        email=data.email,
        notes=data.notes,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    logger.info(f"Client created: {client.id}")
    return client


@router.get("", response_model=ClientListResponse)
async def list_clients(
    search: str | None = Query(None),
    is_lead: bool | None = Query(None),
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Client).where(
        Client.company_id == user.company_id,
        Client.deleted_at.is_(None),
    )

    if search:
        query = query.where(
            or_(
                Client.name.ilike(f"%{search}%"),
                Client.phone.ilike(f"%{search}%"),
                Client.email.ilike(f"%{search}%"),
            )
        )

    if is_lead is not None:
        query = query.where(Client.is_lead == is_lead)

    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    result = await db.execute(
        query.order_by(Client.created_at.desc()).offset(offset).limit(limit)
    )
    clients = result.scalars().all()

    return ClientListResponse(
        clients=[ClientResponse.model_validate(c) for c in clients],
        total=total,
    )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.company_id == user.company_id,
            Client.deleted_at.is_(None),
        )
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("/by-telegram/{telegram_id}", response_model=ClientResponse)
async def get_client_by_telegram(
    telegram_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Client).where(
            Client.company_id == user.company_id,
            Client.telegram_id == telegram_id,
            Client.deleted_at.is_(None),
        )
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: uuid.UUID,
    data: ClientUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.company_id == user.company_id,
            Client.deleted_at.is_(None),
        )
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    await db.commit()
    await db.refresh(client)
    return client
