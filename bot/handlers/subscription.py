import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.access_policy import check_access
from bot.api_client import api
from bot.auth_store import get_auth
from bot.keyboards.inline import subscription_menu, back_to_menu_btn

logger = logging.getLogger(__name__)

router = Router(name="subscription")


@router.message(Command("subscription"))
async def cmd_subscription(message: Message) -> None:
    actor = get_auth(message.from_user.id)
    if actor is None:
        await message.answer("\u26a0\ufe0f Сначала /start.")
        return

    if not check_access("subscription.view", actor.is_admin, actor.active_membership):
        await message.answer("\u26a0\ufe0f Нет доступа.")
        return

    await message.answer("\U0001f4b3 <b>Подписка</b>", reply_markup=subscription_menu())


@router.callback_query(F.data == "subscription_info")
async def subscription_info(callback: CallbackQuery) -> None:
    await callback.answer()
    actor = get_auth(callback.from_user.id)
    if actor is None or actor.active_membership is None:
        await callback.message.edit_text(
            "\u26a0\ufe0f Нет активной компании.", reply_markup=back_to_menu_btn()
        )
        return

    try:
        sub = await api.get_subscription(
            tenant_id=actor.active_membership.company_id,
            telegram_id=actor.telegram_id,
        )
        text = (
            "\U0001f4cb <b>Подписка</b>\n\n"
            f"Тариф: <b>{sub.get('tariff', '—').upper()}</b>\n"
            f"Активна: {'\u2705 Да' if sub.get('active') else '\u274c Нет'}\n"
            f"До: {sub.get('expires_at', '—')}\n"
            f"Автопродление: {'\u2705 Да' if sub.get('auto_renew') else '\u274c Нет'}"
        )
        await callback.message.edit_text(text, reply_markup=back_to_menu_btn())
    except Exception:
        await callback.message.edit_text(
            "\u26a0\ufe0f Не удалось загрузить данные.", reply_markup=back_to_menu_btn()
        )


@router.callback_query(F.data == "subscription_pay")
@router.message(Command("pay"))
async def cmd_pay(event: Message | CallbackQuery) -> None:
    tg_id = event.from_user.id
    actor = get_auth(tg_id)
    if actor is None:
        await _reply(event, "\u26a0\ufe0f Сначала /start.")
        return

    if not check_access("subscription.pay", actor.is_admin, actor.active_membership):
        await _reply(event, "\u26a0\ufe0f Нет доступа.")
        return

    if isinstance(event, CallbackQuery):
        await event.answer()

    company_id = actor.active_membership.company_id
    tariff = actor.active_membership.tariff

    amount_map = {"base": 999, "pro": 2999}
    amount = amount_map.get(tariff, 999)

    try:
        payment = await api.create_payment(
            company_id=company_id,
            tariff=tariff,
            amount=amount,
            return_url="https://t.me/LEADYCRM_bot",
        )
        url = payment.get("payment_url", "")
        text = (
            "\U0001f4b3 <b>Оплата подписки</b>\n\n"
            f"Тариф: <b>{tariff.upper()}</b>\n"
            f"Сумма: <b>{amount} ₽</b>\n\n"
            f"\U0001f517 <a href='{url}'>Перейти к оплате</a>"
        )
        await _reply(event, text)
    except Exception:
        await _reply(event, "\u26a0\ufe0f Ошибка создания платежа. Попробуйте позже.")


async def _reply(event: Message | CallbackQuery, text: str) -> None:
    if isinstance(event, Message):
        await event.answer(text)
    elif isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=back_to_menu_btn())
