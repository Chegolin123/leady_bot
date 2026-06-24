import logging
from decimal import Decimal

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from bot.api_client import api
from bot.keyboards.inline import (
    deals_list_kb, deal_card_kb, trash_kb, back_to_menu_kb
)

logger = logging.getLogger(__name__)
router = Router()


class NewDeal(StatesGroup):
    waiting_title = State()
    waiting_amount = State()


@router.message(Command("new"))
async def cmd_new_deal(message: Message, state: FSMContext):
    await message.answer("Введите <b>название сделки</b>:")
    await state.set_state(NewDeal.waiting_title)


@router.message(NewDeal.waiting_title)
async def deal_title_entered(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) < 2:
        await message.answer("Название должно быть не короче 2 символов.")
        return

    await state.update_data(title=title)
    await message.answer("Введите <b>сумму сделки</b> (или 0):")
    await state.set_state(NewDeal.waiting_amount)


@router.message(NewDeal.waiting_amount)
async def deal_amount_entered(message: Message, state: FSMContext, user: dict = None):
    if not user:
        await message.answer("Сначала зарегистрируйтесь: /start")
        await state.clear()
        return

    try:
        amount = Decimal(message.text.strip().replace(",", "."))
    except Exception:
        await message.answer("Введите число, например: 15000")
        return

    data = await state.get_data()
    title = data.get("title")

    try:
        deal = await api.create_deal(
            str(user["tenant_id"]),
            user["telegram_id"],
            {"title": title, "amount": str(amount), "status": "new"},
        )
        await message.answer(
            f"✅ Сделка создана!\n\n"
            f"<b>#{deal['id'][:8]}</b> — {title}\n"
            f"Сумма: {amount} руб\n"
            f"Статус: new",
            reply_markup=deal_card_kb(deal["id"], "new"),
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Failed to create deal: {e}")
        await message.answer("❌ Ошибка при создании сделки.")
        await state.clear()


@router.message(Command("deals"))
async def cmd_list_deals(message: Message, user: dict = None):
    if not user:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return

    try:
        result = await api.list_deals(str(user["tenant_id"]), user["telegram_id"])
        deals = result.get("deals", [])

        if not deals:
            await message.answer("У вас пока нет сделок.\nСоздайте первую: /new")
            return

        text = "📊 <b>Сделки:</b>\n\n"
        for d in deals:
            text += (
                f"<b>#{d['id'][:8]}</b> — {d['title']}\n"
                f"  Статус: {d['status']} | Сумма: {d.get('amount', '—')} руб\n\n"
            )

        await message.answer(text, reply_markup=deals_list_kb(deals))

    except Exception as e:
        logger.error(f"Failed to list deals: {e}")
        await message.answer("❌ Ошибка загрузки сделок.")


@router.callback_query(F.data.startswith("deal_"))
async def deal_card(callback: CallbackQuery, user: dict = None):
    deal_id = callback.data.replace("deal_", "")

    try:
        deal = await api.get_deal(deal_id, str(user["tenant_id"]), user["telegram_id"])
        text = (
            f"📋 <b>Сделка #{deal['id'][:8]}</b>\n\n"
            f"Название: {deal['title']}\n"
            f"Статус: <b>{deal['status']}</b>\n"
            f"Сумма: {deal.get('amount', '—')} руб\n"
            f"Создана: {deal['created_at'][:10]}"
        )
        await callback.message.edit_text(text, reply_markup=deal_card_kb(deal_id, deal["status"]))
    except Exception as e:
        logger.error(f"Failed to get deal: {e}")
        await callback.answer("Ошибка загрузки сделки.")


@router.callback_query(F.data.startswith("status_"))
async def deal_change_status(callback: CallbackQuery, user: dict = None):
    _, deal_id, new_status = callback.data.split("_", 2)

    try:
        await api.update_deal(
            deal_id, str(user["tenant_id"]), user["telegram_id"],
            {"status": new_status},
        )
        await callback.answer(f"Статус изменен на: {new_status}")

        deal = await api.get_deal(deal_id, str(user["tenant_id"]), user["telegram_id"])
        text = (
            f"📋 <b>Сделка #{deal['id'][:8]}</b>\n\n"
            f"Название: {deal['title']}\n"
            f"Статус: <b>{deal['status']}</b>\n"
            f"Сумма: {deal.get('amount', '—')} руб"
        )
        await callback.message.edit_text(text, reply_markup=deal_card_kb(deal_id, deal["status"]))
    except Exception as e:
        logger.error(f"Failed to change status: {e}")
        await callback.answer("Ошибка смены статуса.")


@router.callback_query(F.data.startswith("delete_"))
async def deal_delete(callback: CallbackQuery, user: dict = None):
    deal_id = callback.data.replace("delete_", "")

    try:
        await api.delete_deal(deal_id, str(user["tenant_id"]), user["telegram_id"])
        await callback.answer("Сделка перемещена в корзину.")
        await callback.message.edit_text(
            f"🗑 Сделка #{deal_id[:8]} перемещена в корзину.\n"
            f"Восстановить: /trash",
            reply_markup=back_to_menu_kb(),
        )
    except Exception as e:
        logger.error(f"Failed to delete deal: {e}")
        await callback.answer("Ошибка удаления.")


@router.message(Command("trash"))
async def cmd_trash(message: Message, user: dict = None):
    if not user:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return

    try:
        result = await api.list_deals(str(user["tenant_id"]), user["telegram_id"], trash=True)
        deals = result.get("deals", [])

        if not deals:
            await message.answer("🗑 Корзина пуста.")
            return

        text = "🗑 <b>Корзина:</b>\n\n"
        for d in deals:
            text += f"<b>#{d['id'][:8]}</b> — {d['title']} | {d.get('amount', '—')} руб\n"

        await message.answer(text, reply_markup=trash_kb(deals))

    except Exception as e:
        logger.error(f"Failed to list trash: {e}")
        await message.answer("❌ Ошибка загрузки корзины.")


@router.callback_query(F.data.startswith("restore_"))
async def deal_restore(callback: CallbackQuery, user: dict = None):
    deal_id = callback.data.replace("restore_", "")

    try:
        await api.restore_deal(deal_id, str(user["tenant_id"]), user["telegram_id"])
        await callback.answer("Сделка восстановлена!")
        await callback.message.edit_text(
            f"✅ Сделка #{deal_id[:8]} восстановлена из корзины.\n/deals — к списку",
            reply_markup=back_to_menu_kb(),
        )
    except Exception as e:
        logger.error(f"Failed to restore deal: {e}")
        await callback.answer("Ошибка восстановления.")
