import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from core.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tickets")

_tickets_store: list[dict] = []


@router.get("")
async def list_company_tickets(user: User = Depends(get_current_user)):
    return [t for t in _tickets_store if t.get("company_id") == str(user.company_id)]


@router.get("/my")
async def list_my_tickets(telegram_id: int, db: AsyncSession = Depends(get_db)):
    return [t for t in _tickets_store if t.get("author_tg") == telegram_id]


@router.post("", status_code=201)
async def create_ticket(
    data: dict,
    user: User = Depends(get_current_user),
):
    ticket = {
        "id": str(len(_tickets_store) + 1),
        "title": data.get("title", ""),
        "text": data.get("text", ""),
        "status": "open",
        "company_id": str(user.company_id) if user.company_id else "",
        "author_tg": user.telegram_id,
        "author_name": user.first_name or str(user.telegram_id),
    }
    _tickets_store.append(ticket)
    return ticket


@router.post("/{ticket_id}/reply")
async def reply_ticket(
    ticket_id: str,
    data: dict,
    user: User = Depends(get_current_user),
):
    for t in _tickets_store:
        if t["id"] == ticket_id:
            t.setdefault("replies", []).append({
                "text": data.get("text", ""),
                "author": user.first_name or str(user.telegram_id),
            })
            return {"ok": True}
    raise HTTPException(status_code=404, detail="Ticket not found")
