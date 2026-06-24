import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.access_policy import check_access
from bot.api_client import api
from bot.auth_store import get_auth
from bot.keyboards.inline import back_to_menu_btn

logger = logging.getLogger(__name__)

router = Router(name="companies")


@router.message(Command("companies"))
async def cmd_companies(message: Message) -> None:
    actor = get_auth(message.from_user.id)
    if actor is None:
        await message.answer("\u26a0\ufe0f Сначала /start.")
        return

    if not actor.company_id:
        await message.answer("\U0001f3e2 У вас пока нет компании. Пройдите онбординг через /start.")
        return

    text = (
        "\U0001f3e2 <b>Ваша компания</b>\n\n"
        f"Название: <b>{actor.company_name}</b>\n"
        f"Тариф: <b>{actor.tariff.upper()}</b>\n"
        f"Роль: <b>{actor.role}</b>"
    )
    await message.answer(text)
