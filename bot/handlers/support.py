import logging

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.access_policy import check_access
from bot.api_client import api
from bot.auth_store import get_auth
from bot.fsm import TicketState
from bot.keyboards.inline import tickets_menu, back_to_menu_btn

logger = logging.getLogger(__name__)

router = Router(name="support")


@router.message(Command("ticket"))
async def cmd_ticket(message: Message, state: FSMContext) -> None:
    actor = get_auth(message.from_user.id)
    if actor is None:
        await message.answer("\u26a0\ufe0f Сначала /start.")
        return

    if not check_access("tickets.create", actor.is_admin, actor.active_membership):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return

    await state.set_state(TicketState.waiting_title)
    await message.answer(
        "\U0001f4dd <b>Новое обращение</b>\n\nВведите тему обращения:"
    )


@router.message(Command("my_tickets"))
async def cmd_my_tickets(message: Message) -> None:
    actor = get_auth(message.from_user.id)
    if actor is None:
        await message.answer("\u26a0\ufe0f Сначала /start.")
        return

    if not check_access("tickets.list_my", actor.is_admin, actor.active_membership):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return

    try:
        tickets = await api.list_my_tickets(telegram_id=actor.telegram_id)
        await _send_ticket_list(message, tickets, "Мои обращения")
    except Exception:
        await message.answer("\u26a0\ufe0f Не удалось загрузить обращения.")


@router.message(Command("tickets"))
async def cmd_tickets(message: Message) -> None:
    actor = get_auth(message.from_user.id)
    if actor is None or actor.active_membership is None:
        await message.answer("\u26a0\ufe0f Нет активной компании.")
        return

    if not check_access("tickets.list_company", actor.is_admin, actor.active_membership):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return

    try:
        tickets = await api.list_company_tickets(
            tenant_id=actor.active_membership.company_id,
            telegram_id=actor.telegram_id,
        )
        await _send_ticket_list(message, tickets, "Обращения компании")
    except Exception:
        await message.answer("\u26a0\ufe0f Не удалось загрузить обращения.")


@router.callback_query(F.data == "tickets_my")
async def tickets_my_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    actor = get_auth(callback.from_user.id)
    if actor is None:
        await callback.message.edit_text("\u26a0\ufe0f Сначала /start.", reply_markup=back_to_menu_btn())
        return
    try:
        tickets = await api.list_my_tickets(telegram_id=actor.telegram_id)
        await _send_ticket_list_callback(callback, tickets, "Мои обращения")
    except Exception:
        await callback.message.edit_text("\u26a0\ufe0f Ошибка.", reply_markup=back_to_menu_btn())


@router.callback_query(F.data == "tickets_company")
async def tickets_company_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    actor = get_auth(callback.from_user.id)
    if actor is None or actor.active_membership is None:
        await callback.message.edit_text("\u26a0\ufe0f Нет активной компании.", reply_markup=back_to_menu_btn())
        return
    try:
        tickets = await api.list_company_tickets(
            tenant_id=actor.active_membership.company_id,
            telegram_id=actor.telegram_id,
        )
        await _send_ticket_list_callback(callback, tickets, "Обращения компании")
    except Exception:
        await callback.message.edit_text("\u26a0\ufe0f Ошибка.", reply_markup=back_to_menu_btn())


@router.callback_query(F.data == "ticket_create")
async def ticket_create_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(TicketState.waiting_title)
    await callback.message.edit_text(
        "\U0001f4dd <b>Новое обращение</b>\n\nВведите тему обращения:",
        reply_markup=back_to_menu_btn(),
    )


@router.message(StateFilter(TicketState.waiting_title), F.text)
async def ticket_title_input(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("\u26a0\ufe0f Тема должна быть не короче 3 символов.")
        return

    await state.update_data(ticket_title=title)
    await state.set_state(TicketState.waiting_text)
    await message.answer("\U0001f4dd Опишите проблему:")


@router.message(StateFilter(TicketState.waiting_text), F.text)
async def ticket_text_input(message: Message, state: FSMContext) -> None:
    actor = get_auth(message.from_user.id)
    if actor is None or actor.active_membership is None:
        await message.answer("\u26a0\ufe0f Нет активной компании.")
        await state.clear()
        return

    data = await state.get_data()
    title = data.get("ticket_title", "")
    text = message.text.strip()
    await state.clear()

    try:
        await api.create_ticket(
            tenant_id=actor.active_membership.company_id,
            telegram_id=actor.telegram_id,
            title=title,
            text=text,
        )
        await message.answer("\u2705 <b>Обращение создано!</b>\nС вами свяжутся менеджеры.")
    except Exception:
        await message.answer("\u26a0\ufe0f Не удалось создать обращение.")


async def _send_ticket_list(event: Message, tickets: list[dict], header: str) -> None:
    if not tickets:
        await event.answer(f"\U0001f4cb <b>{header}</b>\n\nПока нет обращений.")
        return

    lines = [f"\U0001f4cb <b>{header}</b>\n"]
    for t in tickets[:10]:
        status_emoji = {"open": "\U0001f7e1", "closed": "\u2705", "in_progress": "\U0001f535"}.get(
            t.get("status"), "\u2753"
        )
        lines.append(f"{status_emoji} <b>{t.get('title', '—')}</b> — {t.get('status', '—')}")
    await event.answer("\n".join(lines))


async def _send_ticket_list_callback(callback: CallbackQuery, tickets: list[dict], header: str) -> None:
    if not tickets:
        await callback.message.edit_text(
            f"\U0001f4cb <b>{header}</b>\n\nПока нет обращений.",
            reply_markup=back_to_menu_btn(),
        )
        return

    lines = [f"\U0001f4cb <b>{header}</b>\n"]
    for t in tickets[:10]:
        status_emoji = {"open": "\U0001f7e1", "closed": "\u2705", "in_progress": "\U0001f535"}.get(
            t.get("status"), "\u2753"
        )
        lines.append(f"{status_emoji} <b>{t.get('title', '—')}</b> — {t.get('status', '—')}")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_to_menu_btn())
