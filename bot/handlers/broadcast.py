import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.api_client import api
from bot.keyboards.inline import back_to_menu_kb

logger = logging.getLogger(__name__)
router = Router()

_rate_window: deque = deque()
_RATE_LIMIT = 20  # сообщений в секунду


async def _throttle():
    """Троттлинг: не более 20 сообщений в секунду."""
    now = datetime.utcnow()
    while _rate_window and _rate_window[0] < now - timedelta(seconds=1):
        _rate_window.popleft()
    if len(_rate_window) >= _RATE_LIMIT:
        await asyncio.sleep(0.05)
    _rate_window.append(now)


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, user: dict = None):
    if not user:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📢 <b>Рассылка клиентам</b>\n\n"
            "Использование:\n"
            "<code>/broadcast Текст сообщения</code>\n\n"
            "Сообщение будет отправлено всем клиентам с Telegram ID.\n"
            "Лимит: 20 сообщений/сек.",
            reply_markup=back_to_menu_kb(),
        )
        return

    broadcast_text = args[1].strip()

    try:
        clients = await api.list_clients(str(user["tenant_id"]))
        tg_clients = [c for c in clients if c.get("telegram_id")]

        if not tg_clients:
            await message.answer("❌ Нет клиентов с Telegram ID для рассылки.")
            return

        sent = 0
        failed = 0
        status_msg = await message.answer(f"📢 Рассылка: 0/{len(tg_clients)}...")

        for i, client in enumerate(tg_clients):
            try:
                await _throttle()
                await message.bot.send_message(
                    client["telegram_id"],
                    broadcast_text,
                )
                sent += 1
            except Exception as e:
                logger.warning(f"Broadcast to {client['telegram_id']} failed: {e}")
                failed += 1

            if (i + 1) % 10 == 0:
                try:
                    await status_msg.edit_text(f"📢 Рассылка: {i + 1}/{len(tg_clients)}...")
                except Exception:
                    pass

        await status_msg.edit_text(
            f"📢 <b>Рассылка завершена</b>\n\n"
            f"✅ Отправлено: {sent}\n"
            f"❌ Ошибок: {failed}\n"
            f"📊 Всего клиентов: {len(tg_clients)}",
        )
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        await message.answer("❌ Ошибка рассылки. Доступно на тарифе Ultra.")
