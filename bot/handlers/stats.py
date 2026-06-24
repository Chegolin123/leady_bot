import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.access_policy import check_access
from bot.api_client import api
from bot.auth_store import get_auth

logger = logging.getLogger(__name__)

router = Router(name="stats")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    actor = get_auth(message.from_user.id)
    if actor is None:
        await message.answer("\u26a0\ufe0f Сначала /start.")
        return

    if not check_access("stats.view", actor.is_admin, actor.active_membership):
        await message.answer("\u26a0\ufe0f Нет доступа. Статистика доступна на тарифе Pro.")
        return

    if actor.active_membership is None:
        await message.answer("\u26a0\ufe0f Нет активной компании.")
        return

    try:
        summary = await api.analytics_summary(
            tenant_id=actor.active_membership.company_id,
            telegram_id=actor.telegram_id,
        )
        text = (
            "\U0001f4ca <b>Статистика компании</b>\n\n"
            f"\U0001f4c8 Всего сделок: {summary.get('total_deals', '—')}\n"
            f"\u2705 Выигранных: {summary.get('won_deals', '—')}\n"
            f"\U0001f4b0 Выручка: {summary.get('revenue', '—')} \u20bd\n"
            f"\U0001f465 Активных клиентов: {summary.get('active_clients', '—')}\n"
            f"\U0001f4c5 Период: {summary.get('period_days', '—')} дн."
        )
        await message.answer(text)
    except Exception:
        await message.answer("\u26a0\ufe0f Не удалось загрузить статистику.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    actor = get_auth(message.from_user.id)
    is_admin = actor.is_admin if actor else False

    lines = ["\u2753 <b>Справка по командам</b>\n", "<b>Подписка:</b>", "/subscription — информация", "/pay — оплатить", ""]

    if is_admin or (actor and actor.active_membership):
        lines += [
            "<b>Поддержка:</b>",
            "/ticket — создать обращение",
            "/my_tickets — мои обращения",
            "/tickets — обращения компании",
            "/faq — частые вопросы",
            "",
        ]

    if actor and actor.memberships:
        lines += [
            "<b>Компании:</b>",
            "/companies — список компаний",
            "/switch — сменить активную",
            "",
        ]

    if is_admin:
        lines += [
            "<b>Админ:</b>",
            "/admin_companies — компании",
            "/admin_bots — боты",
            "/admin_stats — статистика",
            "/admin_users — пользователи",
            "",
        ]

    lines += [
        "<b>Юридическое:</b>",
        "/revoke_consent — отозвать согласие ПД",
        "/delete_account — удалить аккаунт",
    ]

    await message.answer("\n".join(lines))
