import logging
import re

import httpx
from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from core.config import settings

from bot.api_client import api
from bot.auth_store import get_auth
from bot.fsm import OnboardingState
from bot.keyboards.inline import (
    admin_menu,
    back_to_period_keyboard,
    client_menu,
    consent_keyboard,
    manager_menu,
    onboarding_period_keyboard,
    onboarding_tariff_keyboard,
)
from bot.rich_messages import divider, doc, heading, para, send_rich, table
from bot.services.bot_factory import create_bot as factory_create_bot

logger = logging.getLogger(__name__)

router = Router(name="start")

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{5,32}$")
STOP_WORDS = {
    "admin",
    "support",
    "help",
    "test",
    "root",
    "master",
    "telegram",
    "leady",
    "leadycrm",
    "leady_bot",
    "crm",
    "botfather",
}


async def _get_or_create_actor(from_user) -> dict | None:
    try:
        return await api.get_or_create_actor(
            telegram_id=from_user.id,
            username=from_user.username,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
        )
    except Exception:
        logger.exception("Failed to resolve actor %s", from_user.id)
        return None


def _keyboard_to_dict(markup: InlineKeyboardMarkup) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": button.text,
                    "callback_data": button.callback_data,
                    **({"url": button.url} if button.url else {}),
                }
                for button in row
            ]
            for row in markup.inline_keyboard
        ]
    }


def _tariff_table() -> str:
    return table(
        ["", "BASIC", "PRO"],
        [
            ["Цена в месяц", "999 ₽", "2 999 ₽"],
            ["При оплате за 3 месяца", "2 697 ₽", "8 097 ₽"],
            ["Менеджеры", "1", "10"],
            ["Сделки", "20/мес", "безлимит"],
            ["Статусы сделок", "стандарт", "кастомные"],
            ["Приём платежей", "❌", "✅"],
            ["Аналитика", "❌", "✅"],
            ["Задачи", "❌", "✅"],
        ],
        bordered=True,
        striped=True,
    )


def _pitch_tariff_html() -> str:
    return doc(
        heading(1, "🚀 Leady — CRM в Telegram"),
        para(
            "Telegram — главный канал продаж, но заказы теряются в чатах, "
            "клиенты забываются, сделки не закрываются."
        ),
        para(
            "<b>Leady превращает ваш Telegram-бот в полноценную CRM.</b> "
            "Все сделки, клиенты и задачи — в одном месте, без переключения между сервисами."
        ),
        divider(),
        heading(2, "🔥 Возможности"),
        "<p>• <b>Сделки</b> — ведите клиентов по воронке от заявки до оплаты</p>",
        "<p>• <b>Клиенты</b> — история общения, покупок и контактов</p>",
        "<p>• <b>Задачи</b> — ставьте сотрудникам и контролируйте сроки</p>",
        "<p>• <b>Статистика</b> — выручка, конверсия, средний чек (только PRO)</p>",
        divider(),
        heading(2, "⚡ Как начать"),
        "<p>1. Выберите подходящий тариф</p>",
        "<p>2. Создайте своего бота за 1 минуту</p>",
        "<p>3. Добавьте сотрудников и работайте</p>",
        "<p>4. Клиенты оставляют заявки — вы ничего не теряете</p>",
        divider(),
        heading(2, "💳 Сравнение тарифов"),
        _tariff_table(),
    )


async def _del_msg(bot, chat_id: int, msg_id: int | None) -> None:
    if msg_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass


async def _show_consent(message: Message) -> None:
    await message.answer(
        "📜 <b>Публичная оферта Leady</b>\n\n"
        "📖 <a href='https://leadycrm.ru/offer'>Ознакомиться с полным текстом оферты</a>\n\n"
        "Нажимая ✅ <b>Принимаю</b>, вы подтверждаете полное и безоговорочное принятие условий публичной оферты.",
        reply_markup=consent_keyboard(),
    )


async def _show_client_menu(message: Message, actor_data: dict) -> None:
    bot_username = actor_data.get("bot_username", "")
    company_name = actor_data.get("company_name", "")
    first_name = message.from_user.first_name or ""

    text = (
        f"👋 <b>{first_name}</b>, ваш рабочий бот уже активирован!\n\n"
        f"🏢 Компания: <b>{company_name}</b>\n"
        f"💳 Тариф: <b>{actor_data.get('tariff', 'base').upper()}</b>\n\n"
    )
    if bot_username:
        text += f"🤖 Перейдите в своего бота для работы со сделками и клиентами."
    else:
        text += "🤖 Бот ожидает активации."

    await message.answer(text, reply_markup=client_menu(bot_username))


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    await state.clear()

    actor = get_auth(tg_user.id)
    if actor and actor.is_admin:
        await message.answer(
            f"👋 Добро пожаловать, <b>{tg_user.first_name or ''}</b>!",
            reply_markup=admin_menu(),
        )
        return

    if actor and actor.role == "manager":
        await message.answer(
            f"👋 Добро пожаловать, <b>{tg_user.first_name or ''}</b>!",
            reply_markup=manager_menu(),
        )
        return

    actor_data = await _get_or_create_actor(tg_user)
    if actor_data is None:
        await message.answer("⚠️ Сервис временно недоступен. Попробуйте позже.")
        return

    if not actor_data.get("pd_consent", False):
        await _show_consent(message)
        return

    if actor_data.get("company_id"):
        await _show_client_menu(message, actor_data)
        return

    await state.set_state(OnboardingState.waiting_tariff)
    msg_id = await send_rich(
        message.chat.id,
        _pitch_tariff_html(),
        reply_markup=_keyboard_to_dict(onboarding_tariff_keyboard()),
    )
    if msg_id:
        await state.update_data(prev_msg_id=msg_id)


@router.callback_query(F.data == "consent_accept")
async def consent_accept(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    actor_data = await _get_or_create_actor(callback.from_user)
    if actor_data is None:
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте /start позже.")
        return

    try:
        await api.accept_consent(callback.from_user.id)
    except Exception:
        logger.exception("Failed to persist consent")

    await callback.message.edit_text("✅ <b>Согласие принято!</b>")
    await state.set_state(OnboardingState.waiting_tariff)
    msg_id = await send_rich(
        callback.message.chat.id,
        _pitch_tariff_html(),
        reply_markup=_keyboard_to_dict(onboarding_tariff_keyboard()),
    )
    await _del_msg(callback.bot, callback.message.chat.id, callback.message.message_id)
    if msg_id:
        await state.update_data(prev_msg_id=msg_id)


@router.callback_query(F.data == "consent_decline")
async def consent_decline(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "❌ <b>Согласие не принято.</b>\n\n"
        "⚠️ Без согласия использование бота невозможно.\n"
        "Если передумаете — напишите /start."
    )


@router.callback_query(StateFilter(OnboardingState.waiting_tariff), F.data.startswith("tariff_"))
async def onboarding_tariff(callback: CallbackQuery, state: FSMContext) -> None:
    tariff = callback.data.split("_", 1)[1]
    await callback.answer()
    await state.update_data(tariff=tariff)
    await state.set_state(OnboardingState.waiting_period)
    await callback.message.edit_text(
        f"✅ Тариф: <b>{tariff.upper()}</b>\n\n"
        "📅 <b>Выберите срок:</b>",
        reply_markup=onboarding_period_keyboard(tariff),
    )


@router.callback_query(StateFilter(OnboardingState.waiting_period), F.data.startswith("period_"))
async def onboarding_period(callback: CallbackQuery, state: FSMContext) -> None:
    _, tariff, months_str = callback.data.split("_")
    months = int(months_str)
    await callback.answer()

    prices = {"base": {1: 999, 3: 2697}, "pro": {1: 2999, 3: 8097}}
    amount = prices.get(tariff, {}).get(months, 999)
    period_label = "1 месяц" if months == 1 else "3 месяца"

    await state.update_data(tariff=tariff, months=months, amount=amount)
    await state.set_state(OnboardingState.waiting_company_name)
    msg = await callback.message.edit_text(
        f"✅ Тариф: <b>{tariff.upper()}</b> | {period_label} | <b>{amount} ₽</b>\n\n"
        "🏢 Введите название вашей компании (от 2 до 100 символов):",
        reply_markup=back_to_period_keyboard(),
    )
    await state.update_data(prev_msg_id=msg.message_id)


@router.callback_query(StateFilter(OnboardingState.waiting_company_name), F.data == "back_to_period")
async def onboarding_back_to_period(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    tariff = data.get("tariff", "base")
    await state.set_state(OnboardingState.waiting_period)
    await callback.message.edit_text(
        f"✅ Тариф: <b>{tariff.upper()}</b>\n\n"
        "📅 <b>Выберите срок:</b>",
        reply_markup=onboarding_period_keyboard(tariff),
    )


@router.callback_query(StateFilter(OnboardingState.waiting_period), F.data == "back_to_tariff")
async def onboarding_back_to_tariff(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingState.waiting_tariff)
    msg_id = await send_rich(
        callback.message.chat.id,
        _pitch_tariff_html(),
        reply_markup=_keyboard_to_dict(onboarding_tariff_keyboard()),
    )
    await _del_msg(callback.bot, callback.message.chat.id, callback.message.message_id)
    if msg_id:
        await state.update_data(prev_msg_id=msg_id)


@router.message(StateFilter(OnboardingState.waiting_company_name), F.text)
async def onboarding_company_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    data = await state.get_data()
    prev_msg_id = data.get("prev_msg_id")
    tariff = data.get("tariff", "base")

    if len(name) < 2 or len(name) > 100:
        if prev_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prev_msg_id,
                text="⚠️ Название должно быть от 2 до 100 символов."
            )
        return

    if prev_msg_id:
        await message.bot.edit_message_text(
            chat_id=message.chat.id, message_id=prev_msg_id,
            text="⏳ Создаём компанию..."
        )
    try:
        result = await api.create_company(name=name, tariff=tariff)
        company_id = result.get("id", "")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 409:
            if prev_msg_id:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id, message_id=prev_msg_id,
                    text="⚠️ Компания с таким названием уже существует.\nВведите другое название:"
                )
            return
        logger.exception("Failed to create company")
        if prev_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prev_msg_id,
                text="⚠️ Не удалось создать компанию."
            )
        await state.clear()
        return
    except Exception:
        logger.exception("Failed to create company")
        if prev_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prev_msg_id,
                text="⚠️ Не удалось создать компанию."
            )
        await state.clear()
        return

    await state.update_data(company_id=company_id, company_name=name, tariff=tariff)
    await state.set_state(OnboardingState.waiting_bot_name)
    if prev_msg_id:
        await message.bot.edit_message_text(
            chat_id=message.chat.id, message_id=prev_msg_id,
            text=(
                f"✅ <b>Компания «{name}» создана!</b>\n"
                f"Тариф: <b>{tariff.upper()}</b>\n\n"
                "🤖 Теперь создадим вашего персонального бота.\n"
                "Как назвать бота? Это имя будут видеть ваши клиенты.\n\n"
                "Например: <b>Ромашка CRM</b> или <b>Автосервис Профи</b>\n\n"
                "Введите название бота:"
            ),
            reply_markup=back_to_period_keyboard(),
        )


@router.message(StateFilter(OnboardingState.waiting_bot_name), F.text)
async def onboarding_bot_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    data = await state.get_data()
    prev_msg_id = data.get("prev_msg_id")

    if len(name) < 2 or len(name) > 100:
        if prev_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prev_msg_id,
                text="⚠️ Название должно быть от 2 до 100 символов."
            )
        return

    await state.update_data(bot_name=name)
    await state.set_state(OnboardingState.waiting_bot_username)
    if prev_msg_id:
        await message.bot.edit_message_text(
            chat_id=message.chat.id, message_id=prev_msg_id,
            text=(
                "✏️ <b>Отлично! Теперь придумайте короткое имя для ссылки.</b>\n\n"
                "Ваш бот будет доступен по ссылке:\n"
                "<code>https://t.me/имя_bot</code>\n\n"
                "📌 <b>Требования:</b>\n"
                "• Только латиница (a-z, 0-9, _)\n"
                "• Заканчивается на <code>_bot</code>\n"
                "• 5-32 символа\n\n"
                "Например: <code>romashka_bot</code> или <code>avtoservis_bot</code>"
            )
        )


@router.message(StateFilter(OnboardingState.waiting_bot_username), F.text)
async def onboarding_bot_username(message: Message, state: FSMContext) -> None:
    username = message.text.strip().lower()
    data = await state.get_data()
    prev_msg_id = data.get("prev_msg_id")
    bot_name = data.get("bot_name", "")

    if not USERNAME_RE.match(username):
        if prev_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prev_msg_id,
                text="⚠️ Только латиница, цифры и _. От 5 до 32 символов.\nНапример: <code>romashka_bot</code>"
            )
        return

    if not username.endswith("_bot"):
        suggestion = username.rstrip("bot").rstrip("_") + "_bot"
        if prev_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prev_msg_id,
                text=f"⚠️ Имя должно заканчиваться на <code>_bot</code>.\nПопробуйте: <code>{suggestion}</code>"
            )
        return

    if username in STOP_WORDS or username.rstrip("bot").rstrip("_") in STOP_WORDS:
        if prev_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prev_msg_id,
                text="⚠️ Это имя зарезервировано. Придумайте другое."
            )
        return

    async def _edit(text: str, reply_markup=None) -> None:
        if prev_msg_id:
            kwargs = {"chat_id": message.chat.id, "message_id": prev_msg_id, "text": text}
            if reply_markup:
                kwargs["reply_markup"] = reply_markup
            await message.bot.edit_message_text(**kwargs)

    await _edit("⏳ Проверяем доступность имени...")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            check_url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/getChat?chat_id=@{username}"
            resp = await client.get(check_url)
            resp_data = resp.json()
            if resp_data.get("ok"):
                await _edit(f"⚠️ Имя <b>@{username}</b> уже занято.\nПридумайте другое:")
                return
    except Exception:
        pass

    await state.update_data(bot_username=username)

    await _edit("⏳ Пытаемся создать бота автоматически...")
    try:
        result = await factory_create_bot(bot_name, username)
        if result.get("ok") and result.get("token"):
            await _activate_bot(message, state, prev_msg_id, result["token"], username)
            return
    except Exception:
        logger.exception("Factory create failed")

    await state.set_state(OnboardingState.waiting_bot_token)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[{"text": "🤖 Открыть @BotFather", "url": "https://t.me/BotFather"}]]
    )
    await _edit(
        f"✅ Имя <b>@{username}</b> свободно!\n\n"
        "🤖 <b>Автосоздание пока недоступно, используем BotFather:</b>\n\n"
        f"1️⃣ Отправьте: <code>/newbot</code>\n"
        f"2️⃣ На запрос имени: <code>{bot_name}</code>\n"
        f"3️⃣ На запрос username: <code>{username}</code>\n"
        "4️⃣ Скопируйте <b>токен</b> и вставьте сюда\n\n"
        "<i>Каждую строку отправляйте по одной</i>",
        reply_markup=kb,
    )


@router.message(StateFilter(OnboardingState.waiting_bot_token), F.text)
async def onboarding_bot_token(message: Message, state: FSMContext) -> None:
    token = message.text.strip()
    data = await state.get_data()
    bot_username = data.get("bot_username", "")
    prev_msg_id = data.get("prev_msg_id")

    if ":" not in token or len(token) < 20:
        if prev_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prev_msg_id,
                text=(
                    "⚠️ Это не похоже на токен.\n"
                    "Токен: <code>123456:ABC-DEF1234gh</code>\n"
                    "Скопируйте из @BotFather и вставьте:"
                )
            )
        return

    if prev_msg_id:
        await message.bot.edit_message_text(
            chat_id=message.chat.id, message_id=prev_msg_id,
            text="⏳ Проверяю токен..."
        )
    await _activate_bot(message, state, prev_msg_id, token, bot_username)


async def _activate_bot(
    event: Message,
    state: FSMContext,
    msg_id: int | None,
    token: str,
    bot_username: str,
) -> None:
    async def _edit(text: str, reply_markup=None) -> None:
        if msg_id:
            kwargs = {"chat_id": event.chat.id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
            if reply_markup:
                kwargs["reply_markup"] = reply_markup
            await event.bot.edit_message_text(**kwargs)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            if resp.status_code != 200 or not resp.json().get("ok"):
                raise ValueError("Invalid token")
    except Exception:
        await _edit("⚠️ <b>Токен недействителен.</b>\nПопробуйте снова:")
        return

    await _edit("⏳ Активирую бота...")

    data = await state.get_data()
    company_id = data.get("company_id", "")
    company_name = data.get("company_name", "")

    try:
        await api.admin_add_bot(company_id=company_id, bot_token=token)
    except Exception:
        logger.exception("Failed to activate bot")
        await _edit("⚠️ Не удалось активировать. Попробуйте позже или /start.")
        await state.clear()
        return

    await state.clear()
    first_name = event.from_user.first_name or ""
    await _edit(
        f"🎉 <b>Готово, {first_name}!</b>\n\n"
        f"🏢 Компания: <b>{company_name}</b>\n"
        f"🤖 Ваш бот: <a href='https://t.me/{bot_username}'>@{bot_username}</a>\n\n"
        "👉 Перейдите в него — все сделки, клиенты и задачи там.\n"
        "Этот бот (@LEADYCRM_bot) — для управления подпиской.",
        reply_markup=client_menu(bot_username),
    )
