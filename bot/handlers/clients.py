import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.api_client import api
from bot.keyboards.inline import clients_list_kb, client_actions_kb, back_to_menu_kb

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("clients"))
async def cmd_list_clients(message: Message, user: dict = None):
    if not user:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return

    try:
        result = await api.list_clients(str(user["tenant_id"]), user["telegram_id"])
        clients = result.get("clients", [])

        if not clients:
            await message.answer("У вас пока нет клиентов.\nКлиенты создаются автоматически из входящих сообщений.")
            return

        text = "👥 <b>Клиенты:</b>\n\n"
        for c in clients:
            tag = "🔹" if c.get("is_lead") else "👤"
            text += (
                f"{tag} <b>{c['name']}</b>\n"
                f"  ID: {c['id'][:8]} | Тел: {c.get('phone', '—')}\n\n"
            )

        await message.answer(text, reply_markup=clients_list_kb(clients))

    except Exception as e:
        logger.error(f"Failed to list clients: {e}")
        await message.answer("❌ Ошибка загрузки клиентов.")


@router.callback_query(F.data.startswith("client_"))
async def client_card(callback: CallbackQuery, user: dict = None):
    client_id = callback.data.replace("client_", "")
    await callback.answer()
    await callback.message.edit_text(
        f"👤 Клиент #{client_id[:8]}\nВыберите действие:",
        reply_markup=client_actions_kb(client_id),
    )


@router.callback_query(F.data.startswith("make_lead_"))
async def make_lead(callback: CallbackQuery, user: dict = None):
    client_id = callback.data.replace("make_lead_", "")

    try:
        await api.update_client(
            client_id, str(user["tenant_id"]), user["telegram_id"],
            {"is_lead": True},
        )
        await callback.answer("Клиент → Лид!")
        await callback.message.edit_text(
            f"✅ Клиент #{client_id[:8]} стал лидом.",
            reply_markup=back_to_menu_kb(),
        )
    except Exception as e:
        logger.error(f"Failed to make lead: {e}")
        await callback.answer("Ошибка.")


# ── Входящие сообщения от клиентов → создание «Гостя» ──
@router.message(F.chat.type == "private", ~F.text.startswith("/"))
async def incoming_message(message: Message, user: dict = None):
    if not user:
        return  # Не обрабатываем незарегистрированных

    try:
        # Проверяем, есть ли уже клиент с таким telegram_id
        try:
            client = await api.get_client_by_telegram(
                message.from_user.id,
                str(user["tenant_id"]),
                user["telegram_id"],
            )
            # Клиент уже существует — просто логируем
            logger.debug(f"Message from existing client {client['id']}: {message.text[:50]}")
        except Exception:
            # Создаем нового «Гостя»
            client = await api.create_client(
                str(user["tenant_id"]),
                user["telegram_id"],
                {
                    "name": message.from_user.full_name or "Гость",
                    "telegram_id": message.from_user.id,
                },
            )
            await message.answer(
                f"👤 Создан новый контакт: <b>{client['name']}</b>\n"
                f"Хотите сделать его лидом?",
                reply_markup=client_actions_kb(client["id"]),
            )
            logger.info(f"Guest created from incoming: {client['id']}")

    except Exception as e:
        logger.error(f"Failed to process incoming message: {e}")
