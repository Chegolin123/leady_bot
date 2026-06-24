import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.auth_store import get_auth
from bot.dto import ActorDTO
from bot.keyboards.inline import (
    admin_menu, manager_menu, client_menu, back_to_menu_btn,
)

logger = logging.getLogger(__name__)

router = Router(name="nav")


@router.callback_query(F.data == "back_to_menu")
async def nav_back_to_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    actor: ActorDTO | None = _get_actor(callback)
    if actor is None:
        await callback.message.edit_text("\u26a0\ufe0f Сначала /start.")
        return

    if actor.is_admin:
        kb = admin_menu()
    elif actor.role == "manager":
        kb = manager_menu()
    else:
        kb = client_menu()

    await callback.message.edit_text("\U0001f44b <b>Меню</b>", reply_markup=kb)


# Manager callbacks (stubs)
@router.callback_query(F.data == "manager_tickets")
async def manager_tickets(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "\U0001f4ac <b>Тикеты</b>\n\nРаздел в разработке.",
        reply_markup=back_to_menu_btn(),
    )


@router.callback_query(F.data == "manager_companies")
async def manager_companies(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "\U0001f3e2 <b>Компании</b>\n\nРаздел в разработке.",
        reply_markup=back_to_menu_btn(),
    )


@router.callback_query(F.data == "manager_stats")
async def manager_stats(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "\U0001f4ca <b>Статистика</b>\n\nРаздел в разработке.",
        reply_markup=back_to_menu_btn(),
    )


@router.callback_query(F.data == "manager_help")
async def manager_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "\u2753 <b>Помощь</b>\n\n/admin — админ-панель\n/debug_role — тест ролей",
        reply_markup=back_to_menu_btn(),
    )


# Client callback
@router.callback_query(F.data == "client_subscription")
async def client_subscription(callback: CallbackQuery) -> None:
    await callback.answer()
    actor = _get_actor(callback)
    company = actor.company_name if actor else "—"
    tariff = actor.tariff.upper() if actor else "—"
    await callback.message.edit_text(
        f"\U0001f4cb <b>Подписка</b>\n\n"
        f"Компания: <b>{company}</b>\n"
        f"Тариф: <b>{tariff}</b>",
        reply_markup=back_to_menu_btn(),
    )


def _get_actor(callback: CallbackQuery) -> ActorDTO | None:
    return get_auth(callback.from_user.id) if callback.from_user else None
