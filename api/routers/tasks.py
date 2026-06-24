import logging
import uuid as uuid_mod
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from core.models.task import Task

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def list_tasks(
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403)

    query = select(Task).where(
        Task.company_id == tenant_id, Task.deleted_at.is_(None)
    )
    if status:
        query = query.where(Task.status == status)
    query = query.order_by(Task.due_at.asc().nullslast(), Task.created_at.desc())

    result = await db.execute(query)
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "description": t.description,
            "status": t.status,
            "assignee_id": str(t.assignee_id) if t.assignee_id else None,
            "due_at": t.due_at.isoformat() if t.due_at else None,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]


@router.post("", status_code=201)
async def create_task(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403)

    task = Task(
        company_id=tenant_id,
        title=data["title"],
        description=data.get("description"),
        due_at=datetime.fromisoformat(data["due_at"]) if data.get("due_at") else None,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": str(task.id), "title": task.title, "status": task.status}


@router.patch("/{task_id}")
async def update_task(
    task_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403)

    query = select(Task).where(
        Task.id == task_id, Task.company_id == tenant_id, Task.deleted_at.is_(None)
    )
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404)

    for key in ("title", "description", "status", "due_at"):
        if key in data:
            if key == "due_at" and data[key]:
                setattr(task, key, datetime.fromisoformat(data[key]))
            else:
                setattr(task, key, data[key])

    await db.commit()
    return {"id": str(task.id), "status": task.status}


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403)

    query = select(Task).where(
        Task.id == task_id, Task.company_id == tenant_id
    )
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404)

    task.deleted_at = datetime.utcnow()
    await db.commit()
