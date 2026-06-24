import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.access_policy import check_access
from bot.api_client import api
from bot.auth_store import get_auth
from bot.keyboards.inline import admin_menu, back_to_menu_btn
from bot.rich_messages import (
    doc, heading, para, bold, table, divider, send_rich,
)

logger = logging.getLogger(__name__)

router = Router(name="admin")


def _is_admin(event) -> bool:
    actor = get_auth(event.from_user.id)
    if actor is None:
        return False
    return actor.is_admin


# ══════════════════════════════════════════════════════════════════════
# АДМИН-МЕНЮ
# ══════════════════════════════════════════════════════════════════════

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return
    await message.answer("\U0001f6e0 <b>Администрирование</b>", reply_markup=admin_menu())


@router.callback_query(F.data == "menu_admin")
async def menu_admin_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if not _is_admin(callback):
        await callback.message.edit_text("\u26a0\ufe0f Нет доступа.", reply_markup=back_to_menu_btn())
        return
    await callback.message.edit_text("\U0001f6e0 <b>Администрирование</b>", reply_markup=admin_menu())


# ══════════════════════════════════════════════════════════════════════
# КОМПАНИИ
# ══════════════════════════════════════════════════════════════════════

@router.message(Command("admin_companies"))
async def cmd_admin_companies(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return
    try:
        data = await api.admin_list_companies()
        companies = data.get("companies", data) if isinstance(data, dict) else data
        await _send_company_list(message, companies)
    except Exception:
        await message.answer("\u26a0\ufe0f Ошибка загрузки компаний.")


@router.callback_query(F.data == "admin_companies")
async def admin_companies_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if not _is_admin(callback):
        await callback.message.edit_text("\u26a0\ufe0f Нет доступа.", reply_markup=back_to_menu_btn())
        return
    try:
        data = await api.admin_list_companies()
        items = data.get("companies", data) if isinstance(data, dict) else data
        await _send_company_list_callback(callback, items)
    except Exception:
        await callback.message.edit_text("\u26a0\ufe0f Ошибка.", reply_markup=back_to_menu_btn())


# ══════════════════════════════════════════════════════════════════════
# СТАТИСТИКА (ADMIN)
# ══════════════════════════════════════════════════════════════════════

@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return
    await _show_admin_stats(message)


@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if not _is_admin(callback):
        await callback.message.edit_text("\u26a0\ufe0f Нет доступа.", reply_markup=back_to_menu_btn())
        return
    await _show_admin_stats_callback(callback)


async def _show_admin_stats(event: Message) -> None:
    try:
        companies_data = await api.admin_list_companies()
        companies = companies_data.get("companies", companies_data) if isinstance(companies_data, dict) else companies_data

        total = len(companies)
        base_count = sum(1 for c in companies if c.get("tariff") == "base")
        pro_count = sum(1 for c in companies if c.get("tariff") == "pro")
        base_rev = base_count * 999
        pro_rev = pro_count * 2999
        total_rev = base_rev + pro_rev
        avg = _avg_check(base_count, pro_count)
        popular = "Pro" if pro_count > base_count else "Base"
        popular_pct = max(base_count, pro_count) * 100 // max(total, 1)

        rich = doc(
            heading(1, "📊 Системная статистика"),
            table(
                ["Показатель", "Значение"],
                [
                    ["🏢 Всего компаний", str(total)],
                    ["   ├ Базовый", str(base_count)],
                    ["   └ Pro", str(pro_count)],
                    ["💰 Выручка (расчётная)", f"{total_rev} ₽"],
                    ["   ├ Base", f"{base_rev} ₽"],
                    ["   └ Pro", f"{pro_rev} ₽"],
                    ["📊 Средний чек", f"{avg} ₽"],
                    ["📈 Популярный тариф", f"{popular} ({popular_pct}%)"],
                ],
                bordered=True,
                striped=True,
            ),
        )

        ok = await send_rich(event.chat.id, rich)
        if not ok:
            text = (
                "📊 <b>Системная статистика</b>\n\n"
                f"🏢 Всего компаний: <b>{total}</b>\n"
                f"   Базовый: {base_count} | Pro: {pro_count}\n\n"
                f"💰 Выручка: <b>{total_rev} ₽</b>\n"
                f"📊 Средний чек: <b>{avg} ₽</b>\n"
                f"📈 Тариф: <b>{popular} ({popular_pct}%)</b>"
            )
            await event.answer(text)
    except Exception:
        await event.answer("⚠️ Ошибка загрузки статистики.")


async def _show_admin_stats_callback(callback: CallbackQuery) -> None:
    try:
        companies_data = await api.admin_list_companies()
        companies = companies_data.get("companies", companies_data) if isinstance(companies_data, dict) else companies_data
        total = len(companies)
        base_count = sum(1 for c in companies if c.get("tariff") == "base")
        pro_count = sum(1 for c in companies if c.get("tariff") == "pro")

        text = (
            "\U0001f4ca <b>Системная статистика</b>\n\n"
            f"\U0001f3e2 Всего компаний: <b>{total}</b>\n"
            f"   Базовый: {base_count}\n"
            f"   Pro: {pro_count}\n\n"
            f"\U0001f4b0 Выручка (расчётная): <b>{base_count * 999 + pro_count * 2999} \u20bd</b>\n"
            f"\U0001f4ca Средний чек: <b>{_avg_check(base_count, pro_count)} \u20bd</b>"
        )
        await callback.message.edit_text(text, reply_markup=back_to_menu_btn())
    except Exception:
        await callback.message.edit_text("\u26a0\ufe0f Ошибка.", reply_markup=back_to_menu_btn())


def _avg_check(base: int, pro: int) -> int:
    total = base + pro
    if total == 0:
        return 0
    return (base * 999 + pro * 2999) // total


# ══════════════════════════════════════════════════════════════════════
# БОТЫ
# ══════════════════════════════════════════════════════════════════════

@router.message(Command("admin_bots"))
async def cmd_admin_bots(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return
    try:
        bots = await api.admin_list_bots()
        if not bots:
            await message.answer("\U0001f916 <b>Боты</b>\n\nПока нет зарегистрированных ботов.")
            return
        lines = ["\U0001f916 <b>Боты</b>\n"]
        for b in bots[:15]:
            lines.append(f"\U0001f916 {b.get('bot_name', b.get('name', '—'))} | {b.get('status', '—')}")
        await message.answer("\n".join(lines))
    except Exception:
        await message.answer("\u26a0\ufe0f Ошибка загрузки.")


@router.callback_query(F.data == "admin_bots")
async def admin_bots_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if not _is_admin(callback):
        await callback.message.edit_text("\u26a0\ufe0f Нет доступа.", reply_markup=back_to_menu_btn())
        return
    try:
        bots = await api.admin_list_bots()
        count = len(bots) if bots else 0
        await callback.message.edit_text(
            f"\U0001f916 <b>Боты</b>\n\nЗарегистрировано: {count}\n\n/admin_bots — подробнее",
            reply_markup=back_to_menu_btn(),
        )
    except Exception:
        await callback.message.edit_text("\u26a0\ufe0f Ошибка.", reply_markup=back_to_menu_btn())


# ══════════════════════════════════════════════════════════════════════
# ПОЛЬЗОВАТЕЛИ
# ══════════════════════════════════════════════════════════════════════

@router.message(Command("admin_users"))
async def cmd_admin_users(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return
    try:
        users = await api.admin_list_users()
        if not users:
            await message.answer("\U0001f465 <b>Пользователи</b>\n\nСписок пуст.")
            return
        lines = ["\U0001f465 <b>Пользователи</b>\n"]
        for u in users[:15]:
            lines.append(
                f"\U0001f464 {u.get('first_name', '—')} "
                f"(@{u.get('username', '—')}) — {u.get('role', '—')}"
            )
        await message.answer("\n".join(lines))
    except Exception:
        await message.answer("\u26a0\ufe0f Ошибка загрузки.")


@router.callback_query(F.data == "admin_users")
async def admin_users_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if not _is_admin(callback):
        await callback.message.edit_text("\u26a0\ufe0f Нет доступа.", reply_markup=back_to_menu_btn())
        return
    await callback.message.edit_text(
        "\U0001f465 <b>Пользователи</b>\n\n/admin_users — список",
        reply_markup=back_to_menu_btn(),
    )


# ══════════════════════════════════════════════════════════════════════
# ПЛАТЕЖИ, ТИКЕТЫ, ЛОГИ
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_tickets")
async def admin_tickets_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "\U0001f4ac <b>Тикеты</b>\n\nРаздел в разработке.",
        reply_markup=back_to_menu_btn(),
    )


@router.message(Command("admin_payments"))
async def cmd_admin_payments(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return
    await message.answer("\U0001f4b3 <b>Платежи</b>\n\nРаздел в разработке.")


@router.message(Command("admin_logs"))
async def cmd_admin_logs(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return
    await message.answer("\U0001f4cb <b>Логи</b>\n\nРаздел в разработке.")


@router.message(Command("admin_block"))
async def cmd_admin_block(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return
    await message.answer("\U0001f6ab <b>Блокировка</b>\n\nРаздел в разработке.")


@router.message(Command("admin_unblock"))
async def cmd_admin_unblock(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return
    await message.answer("\u2705 <b>Разблокировка</b>\n\nРаздел в разработке.")


@router.message(Command("admin_delete"))
async def cmd_admin_delete(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return
    await message.answer("\u274c <b>Удаление</b>\n\nРаздел в разработке.")


@router.message(Command("admin_restore"))
async def cmd_admin_restore(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return
    await message.answer("\U0001f504 <b>Восстановление</b>\n\nРаздел в разработке.")


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

async def _send_company_list(message: Message, companies: list[dict]) -> None:
    if not companies:
        await message.answer("\U0001f3e2 <b>Компании</b>\n\nСписок пуст.")
        return
    lines = ["\U0001f3e2 <b>Компании</b>\n"]
    for c in companies[:15]:
        lines.append(f"\U0001f3e2 {c.get('name', '—')} | {c.get('tariff', '—')}")
    await message.answer("\n".join(lines))


async def _send_company_list_callback(callback: CallbackQuery, companies: list[dict]) -> None:
    if not companies:
        await callback.message.edit_text("\U0001f3e2 <b>Компании</b>\n\nСписок пуст.", reply_markup=back_to_menu_btn())
        return
    lines = ["\U0001f3e2 <b>Компании</b>\n"]
    for c in companies[:15]:
        lines.append(f"\U0001f3e2 {c.get('name', '—')} | {c.get('tariff', '—')}")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_to_menu_btn())
