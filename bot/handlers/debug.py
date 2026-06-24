"""Temporary debug commands for testing roles."""

import json

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from redis.asyncio import Redis

from bot.auth_store import get_auth, set_auth
from bot.keyboards.inline import admin_menu, manager_menu, client_menu
from core.config import settings

router = Router(name="debug")

VALID_ROLES = {"guest", "client", "manager", "admin"}


async def _cache_role(telegram_id: int, role: str, is_admin: bool, company_id: str | None, company_name: str, tariff: str) -> None:
    try:
        redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        payload = {
            "actor_id": "",
            "telegram_id": telegram_id,
            "is_admin": is_admin,
            "pd_consent": True,
            "role": role,
            "company_id": company_id or "",
            "company_name": company_name,
            "tariff": tariff,
        }
        await redis.setex(f"user:{telegram_id}", settings.USER_CACHE_TTL, json.dumps(payload))
        await redis.close()
    except Exception:
        pass


@router.message(Command("debug_role"))
async def cmd_debug_role(message: Message) -> None:
    if not message.from_user:
        return

    actor = get_auth(message.from_user.id)
    if actor is None:
        await message.answer("\u26a0\ufe0f Сначала /start.")
        return

    if not actor.is_admin:
        await message.answer("\u26a0\ufe0f Только для админов.")
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        current = "admin" if actor.is_admin else actor.role
        await message.answer(
            "\U0001f6e0 <b>Debug: смена роли</b>\n\n"
            f"Текущая: <b>{current}</b>\n\n"
            "<code>/debug_role guest</code>\n"
            "<code>/debug_role client</code>\n"
            "<code>/debug_role manager</code>\n"
            "<code>/debug_role admin</code>"
        )
        return

    role = parts[1].lower()
    if role not in VALID_ROLES:
        await message.answer(f"\u26a0\ufe0f Допустимые: {', '.join(VALID_ROLES)}")
        return

    tg_id = message.from_user.id

    if role == "admin":
        actor.is_admin = True
        actor.role = "admin"
        await set_auth(tg_id, actor)
        await _cache_role(tg_id, "admin", True, actor.company_id, actor.company_name, actor.tariff)
        await message.answer("\u2705 Роль: <b>ADMIN</b>", reply_markup=admin_menu())

    elif role == "manager":
        actor.is_admin = False
        actor.role = "manager"
        await set_auth(tg_id, actor)
        await _cache_role(tg_id, "manager", False, actor.company_id, actor.company_name, actor.tariff)
        await message.answer("\u2705 Роль: <b>MANAGER</b>", reply_markup=manager_menu())

    elif role == "client":
        actor.is_admin = False
        actor.role = "client"
        if not actor.company_id:
            actor.company_id = "test-company-0001"
            actor.company_name = "Тестовая Компания"
            actor.tariff = "pro"
        await set_auth(tg_id, actor)
        await _cache_role(tg_id, "client", False, actor.company_id, actor.company_name, actor.tariff)
        await message.answer(
            "\u2705 Роль: <b>CLIENT</b>\n"
            f"Компания: <b>{actor.company_name}</b>",
            reply_markup=client_menu("TestCompanyBot"),
        )

    elif role == "guest":
        actor.is_admin = False
        actor.role = "guest"
        actor.company_id = None
        actor.company_name = ""
        await set_auth(tg_id, actor)
        await _cache_role(tg_id, "guest", False, None, "", "base")
        await message.answer(
            "\u2705 Роль: <b>GUEST</b>\n\n"
            "Гость видит только онбординг. Напишите /start чтобы пройти покупку."
        )
