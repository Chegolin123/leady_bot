import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.access_policy import check_access
from bot.api_client import api
from bot.auth_store import get_auth

logger = logging.getLogger(__name__)

router = Router(name="legal")


@router.message(Command("revoke_consent"))
async def cmd_revoke_consent(message: Message) -> None:
    actor = get_auth(message.from_user.id)
    if actor is None:
        await message.answer("\u26a0\ufe0f Сначала /start.")
        return

    if not check_access("legal.revoke_consent", actor.is_admin, actor.active_membership):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return

    try:
        await api.revoke_consent(telegram_id=actor.telegram_id)
        await message.answer(
            "\u2705 <b>Согласие на обработку ПД отозвано.</b>\n\n"
            "Дальнейшее использование бота ограничено.\n"
            "Для возобновления — напишите /start."
        )
    except Exception:
        await message.answer("\u26a0\ufe0f Не удалось выполнить операцию. Попробуйте позже.")


@router.message(Command("delete_account"))
async def cmd_delete_account(message: Message) -> None:
    actor = get_auth(message.from_user.id)
    if actor is None:
        await message.answer("\u26a0\ufe0f Сначала /start.")
        return

    if not check_access("legal.delete_account", actor.is_admin, actor.active_membership):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return

    try:
        await api.request_account_deletion(telegram_id=actor.telegram_id)
        await message.answer(
            "\u2705 <b>Заявка на удаление аккаунта принята.</b>\n\n"
            "Ваши данные будут удалены в соответствии с регламентом.\n"
            "Обычно это занимает до 30 дней."
        )
    except Exception:
        await message.answer("\u26a0\ufe0f Не удалось подать заявку. Попробуйте позже.")
