import asyncio
import logging
import os
import re
import time
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    logger.critical("BOT_TOKEN не задан! Передайте через переменную окружения.")
    exit(1)

MAX_DEALS_PER_USER = 200
MAX_NAME_LENGTH = 200
MAX_TITLE_LENGTH = 500
MAX_INPUT_ATTEMPTS = 3

router = Router()

companies: dict = {}
deals_by_user: dict[int, list] = {}
user_state: dict = {}

# Дедупликация: трекаем последнее сообщение пользователя
_last_msg: dict[int, tuple[str, float]] = {}

def is_duplicate(message: Message | CallbackQuery) -> bool:
    """True если это сообщение — дубль (тот же текст от того же пользователя < 3 сек назад)."""
    if isinstance(message, CallbackQuery):
        return False
    uid = message.from_user.id
    text = (message.text or "").strip()
    key = f"{uid}:{text}"
    now = time.time()
    last_key, last_time = _last_msg.get(uid, ("", 0))
    if key == last_key and now - last_time < 3:
        logger.warning(f"Duplicate blocked: user={uid}, text={text[:40]}")
        return True
    _last_msg[uid] = (key, now)
    return False


class Onboarding(StatesGroup):
    waiting_company_name = State()
    waiting_tariff = State()


class NewDeal(StatesGroup):
    waiting_title = State()
    waiting_amount = State()


def validate_name(name: str) -> str | None:
    name = name.strip()
    if not name:
        return "Название не может быть пустым."
    if len(name) < 2:
        return "Название должно содержать минимум 2 символа."
    if len(name) > MAX_NAME_LENGTH:
        return f"Название не должно превышать {MAX_NAME_LENGTH} символов."
    if re.search(r"[<>\"'&]", name):
        return "Название содержит недопустимые символы (< > \" ' &)."
    return None


def validate_deal_title(title: str) -> str | None:
    title = title.strip()
    if not title:
        return "Название сделки не может быть пустым."
    if len(title) < 2:
        return "Название сделки должно содержать минимум 2 символа."
    if len(title) > MAX_TITLE_LENGTH:
        return f"Название не должно превышать {MAX_TITLE_LENGTH} символов."
    if re.search(r"[<>\"'&]", title):
        return "Название содержит недопустимые символы (< > \" ' &)."
    return None


def validate_amount(value: str) -> float | str:
    value = value.strip().replace(",", ".")
    if not value:
        return "Сумма не может быть пустой."
    try:
        amount = float(value)
    except ValueError:
        return "Введите число, например: 15000 или 0."
    if amount < 0:
        return "Сумма не может быть отрицательной."
    if amount > 1_000_000_000:
        return "Сумма слишком большая (максимум 1 млрд)."
    return amount


def get_user_deals(user_id: int) -> list:
    if user_id not in deals_by_user:
        deals_by_user[user_id] = []
    return deals_by_user[user_id]


def count_user_deals(user_id: int) -> int:
    return len(get_user_deals(user_id))


# ── Клавиатуры ──
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Сделки", callback_data="menu_deals")],
        [InlineKeyboardButton(text="➕ Новая сделка", callback_data="new_deal")],
        [InlineKeyboardButton(text="👥 Клиенты", callback_data="menu_clients")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings")],
    ])


def consent_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю", callback_data="consent_accept")],
        [InlineKeyboardButton(text="❌ Отказываюсь", callback_data="consent_decline")],
    ])


def tariff_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 Базовый — 999 руб/мес", callback_data="tariff_base")],
        [InlineKeyboardButton(text="🚀 Pro — 2 999 руб/мес", callback_data="tariff_pro")],
    ])


def deal_card_kb(deal_id: int, status: str):
    statuses = ["new", "in_progress", "invoice_sent", "won", "lost"]
    status_labels = {
        "new": "Новая сделка",
        "in_progress": "В работе",
        "invoice_sent": "Счёт выставлен",
        "won": "Завершено",
        "lost": "Отказ",
    }
    kb = []
    row = []
    for s in statuses:
        label = f"✅ {status_labels[s]}" if s == status else status_labels[s]
        row.append(InlineKeyboardButton(text=label, callback_data=f"status_{deal_id}_{s}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{deal_id}")])
    kb.append([InlineKeyboardButton(text="« Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« В меню", callback_data="back_to_menu")]
    ])


def pricing_info_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Попробовать 1 неделю бесплатно", callback_data="start_onboarding")],
        [InlineKeyboardButton(text="💳 Смотреть тарифы", callback_data="show_pricing")],
        [InlineKeyboardButton(text="📋 Демо: как это работает", callback_data="show_demo")],
    ])

def start_onboarding_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, создать компанию", callback_data="start_onboarding")],
        [InlineKeyboardButton(text="📋 Показать демо", callback_data="show_demo")],
    ])

# ── /start ──
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if is_duplicate(message):
        return
    tid = message.from_user.id
    if tid in user_state and user_state[tid].get("company"):
        await message.answer(
            f"👋 С возвращением! Вы работаете в компании «{user_state[tid]['company']}».",
            reply_markup=main_menu_kb(),
        )
        return

    text = (
        "🤖 <b>Leady — CRM в Telegram</b>\n\n"
        "Управляй сделками и клиентами прямо в мессенджере.\n\n"
        "Перед началом ознакомьтесь с офертой:\n"
        "📄 <a href='https://leadycrm.ru/offer'>Публичная оферта</a>\n\n"
        "<b>Нажимая «Принимаю», вы даёте согласие на обработку ПД</b> (152-ФЗ).\n"
        "Отозвать: /revoke_consent | Удалить: /delete_account\n\n"
        "⚠️ <i>Это тестовая MVP-версия. Данные хранятся в памяти и могут быть потеряны при перезапуске.</i>"
    )
    await message.answer(text, reply_markup=consent_kb(), disable_web_page_preview=True)


@router.callback_query(F.data == "consent_accept")
async def consent_accept(callback: CallbackQuery, state: FSMContext):
    if is_duplicate(callback):
        return
    tid = callback.from_user.id
    user_state[tid] = {"pd_consent": True, "input_attempts": 0}

    text = (
        "✅ <b>Согласие принято!</b>\n\n"
        "<b>Что вы получаете с Leady:</b>\n\n"
        "📊 <b>Сделки</b> — создавайте за 2 минуты, двигайте по воронке\n"
        "👥 <b>Клиенты</b> — автосоздание из входящих сообщений\n"
        "📋 <b>5 статусов</b> — Новая → В работе → Счёт → Завершено → Отказ\n"
        "🔗 <b>Менеджеры</b> — приглашение по коду\n"
        "🔒 <b>Безопасность</b> — 152-ФЗ, данные в РФ\n\n"
        "<b>💰 Тарифы:</b>\n"
        "• Базовый — <b>999 руб/мес</b> (1 менеджер, до 30 лидов)\n"
        "• Pro — <b>2 999 руб/мес</b> (10 менеджеров, YooKassa)\n\n"
        "🎁 <b>1 неделя бесплатно</b> на Базовом тарифе.\n"
        "Скидка 20% на первый месяц любой подписки.\n"
        "💎 При оплате за квартал — скидка 10%.\n\n"
        "<i>Никаких контрактов. Отменить можно в любой момент.</i>\n\n"
        "📄 <a href='https://leadycrm.ru'>Ознакомиться подробнее на сайте</a>"
    )
    await callback.message.edit_text(text, reply_markup=start_onboarding_kb(), disable_web_page_preview=True)


@router.callback_query(F.data == "show_demo")
async def show_demo(callback: CallbackQuery):
    if is_duplicate(callback):
        return
    text = (
        "📋 <b>Как работает Leady:</b>\n\n"
        "<b>1.</b> Вы регистрируете компанию (1 минута)\n"
        "<b>2.</b> Создаёте сделку: /new → название → сумма\n"
        "<b>3.</b> Двигаете её по статусам:\n"
        "    Новая сделка → В работе → Счёт → Завершено\n"
        "<b>4.</b> Приглашаете менеджеров: /invite → код\n"
        "<b>5.</b> Клиенты создаются автоматически из входящих\n\n"
        "<b>Сценарий за 2 минуты:</b>\n"
        "Клиент пишет в Telegram → автосоздание контакта →\n"
        "менеджер создаёт сделку → меняет статус →\n"
        "владелец видит воронку в реальном времени.\n\n"
        "<i>Всё внутри Telegram. Ничего устанавливать не надо.</i>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Попробовать бесплатно", callback_data="start_onboarding")],
            [InlineKeyboardButton(text="« Назад", callback_data="consent_accept")],
        ]),
    )


@router.callback_query(F.data == "show_pricing")
async def show_pricing(callback: CallbackQuery):
    if is_duplicate(callback):
        return
    text = (
        "💳 <b>Тарифы Leady</b>\n\n"
        "<b>Базовый — 999 руб/мес</b>\n"
        "• 1 менеджер\n"
        "• Сделки со статусами\n"
        "• Контакты клиентов\n"
        "• До 30 лидов/мес\n"
        "• 1 неделя бесплатно\n\n"
        "<b>Pro — 2 999 руб/мес</b>\n"
        "• Всё из Базового\n"
        "• 10 менеджеров\n"
        "• Кастомные статусы\n"
        "• Встроенная оплата YooKassa\n"
        "• Скидка 20% на первый месяц\n\n"
        "<b>💎 Квартал (3 мес, –10%):</b>\n"
        "• Базовый: 2 697 руб (899 руб/мес)\n"
        "• Pro: 8 097 руб (2 699 руб/мес)\n\n"
        "<b>Ultra — по запросу</b>\n"
        "• Свой бот, веб-кабинет, без лимитов\n\n"
        "<i>Без контрактов. Отмена в любой момент.\n"
        "Оплата через YooKassa с чеком (54-ФЗ).</i>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать бесплатно", callback_data="start_onboarding")],
            [InlineKeyboardButton(text="« Назад", callback_data="consent_accept")],
        ]),
    )


@router.callback_query(F.data == "start_onboarding")
async def start_onboarding(callback: CallbackQuery, state: FSMContext):
    if is_duplicate(callback):
        return
    await callback.message.edit_text(
        "🏢 <b>Создание компании</b>\n\n"
        "Введите <b>название вашей компании</b>.\n\n"
        "<i>Например: «Автосервис на Ленина», «Салон красоты Марии»</i>"
    )
    await state.set_state(Onboarding.waiting_company_name)


@router.callback_query(F.data == "consent_decline")
async def consent_decline(callback: CallbackQuery):
    if is_duplicate(callback):
        return
    await callback.message.edit_text("❌ Без согласия на обработку ПД использование невозможно.\n/start — попробовать снова.")


@router.message(Onboarding.waiting_company_name)
async def company_name(message: Message, state: FSMContext):
    if is_duplicate(message):
        return
    tid = message.from_user.id
    error = validate_name(message.text)
    if error:
        attempts = user_state.get(tid, {}).get("input_attempts", 0) + 1
        user_state.setdefault(tid, {})["input_attempts"] = attempts
        if attempts >= MAX_INPUT_ATTEMPTS:
            await message.answer("❌ Слишком много неудачных попыток. Используйте /start чтобы начать заново.")
            await state.clear()
            return
        await message.answer(f"❌ {error} Попробуйте снова (осталось попыток: {MAX_INPUT_ATTEMPTS - attempts}).")
        return

    name = message.text.strip()
    user_state[tid]["input_attempts"] = 0
    await state.update_data(company_name=name)
    await message.answer(
        "💳 <b>Выберите тариф:</b>\n\n"
        "<b>Базовый</b> — 999 руб/мес\n"
        "• 1 менеджер\n"
        "• Сделки со статусами\n"
        "• До 30 лидов/мес\n"
        "• 1 неделя бесплатно\n\n"
        "<b>Pro</b> — 2 999 руб/мес\n"
        "• 10 менеджеров\n"
        "• Кастомные статусы\n"
        "• Встроенная оплата YooKassa\n"
        "• Скидка 20% на первый месяц",
        reply_markup=tariff_kb(),
    )
    await state.set_state(Onboarding.waiting_tariff)


@router.callback_query(Onboarding.waiting_tariff, F.data.startswith("tariff_"))
async def tariff_chosen(callback: CallbackQuery, state: FSMContext):
    if is_duplicate(callback):
        return
    tariff = callback.data.split("_")[1]
    data = await state.get_data()
    name = data.get("company_name")
    tid = callback.from_user.id

    user_state[tid] = {**user_state.get(tid, {}), "company": name, "tariff": tariff}

    await callback.message.edit_text(
        f"✅ <b>Компания создана!</b>\n\n"
        f"🏢 {name}\n"
        f"📦 Тариф: {tariff.upper()}\n\n"
        f"Создайте первую сделку: /new\n"
        f"Пригласите менеджера: /invite\n\n"
        f"⚠️ <i>Это тестовая MVP-версия. Данные хранятся в памяти "
        f"и могут быть потеряны при перезапуске бота.</i>",
        reply_markup=main_menu_kb(),
    )
    await state.clear()
    logger.info(f"Компания создана: {name}, тариф={tariff}, пользователь={tid}")


# ── /new ──
@router.callback_query(F.data == "new_deal")
async def new_deal_btn(callback: CallbackQuery, state: FSMContext):
    if is_duplicate(callback):
        return
    tid = callback.from_user.id
    if tid not in user_state or not user_state[tid].get("company"):
        await callback.answer("❌ Сначала зарегистрируйтесь: /start")
        return

    deal_count = count_user_deals(tid)
    if deal_count >= MAX_DEALS_PER_USER:
        await callback.message.edit_text(
            f"❌ <b>Достигнут лимит сделок:</b> {MAX_DEALS_PER_USER}.\n"
            f"У вас {deal_count} сделок. Удалите старые, чтобы создать новые.",
            reply_markup=back_kb(),
        )
        return

    await callback.message.edit_text(
        f"Введите <b>название сделки</b> (осталось слотов: {MAX_DEALS_PER_USER - deal_count}):"
    )
    await state.set_state(NewDeal.waiting_title)


@router.message(NewDeal.waiting_title)
async def deal_title(message: Message, state: FSMContext):
    if is_duplicate(message):
        return
    error = validate_deal_title(message.text)
    if error:
        await message.answer(f"❌ {error} Попробуйте снова.")
        return
    await state.update_data(title=message.text.strip())
    await message.answer("Введите <b>сумму сделки</b> (или 0):")
    await state.set_state(NewDeal.waiting_amount)


@router.message(NewDeal.waiting_amount)
async def deal_amount(message: Message, state: FSMContext):
    if is_duplicate(message):
        return
    result = validate_amount(message.text)
    if isinstance(result, str):
        await message.answer(f"❌ {result} Попробуйте снова.")
        return

    amount = result
    data = await state.get_data()
    tid = message.from_user.id

    deal = {
        "id": len(get_user_deals(tid)) + 1,
        "title": data["title"],
        "amount": amount,
        "status": "new",
        "user_id": tid,
    }
    get_user_deals(tid).append(deal)

    await message.answer(
        f"✅ <b>Сделка создана!</b>\n\n"
        f"<b>#{deal['id']}</b> — {deal['title']}\n"
        f"Сумма: {deal['amount']:,.0f} руб\n"
        f"Статус: Новый",
        reply_markup=deal_card_kb(deal["id"], "new"),
    )
    await state.clear()


# ── /deals ──
@router.callback_query(F.data == "menu_deals")
async def menu_deals(callback: CallbackQuery):
    if is_duplicate(callback):
        return
    tid = callback.from_user.id
    user_deals = get_user_deals(tid)

    if not user_deals:
        await callback.message.edit_text(
            "У вас пока нет сделок.\nСоздайте первую: /new",
            reply_markup=back_kb(),
        )
        return

    text = f"📊 <b>Сделки</b> ({len(user_deals)}/{MAX_DEALS_PER_USER}):\n\n"
    buttons = []
    for d in user_deals[-10:]:
        text += f"<b>#{d['id']}</b> — {d['title']} | {d['status']} | {d['amount']:,.0f} руб\n"
        buttons.append([
            InlineKeyboardButton(text=f"📋 {d['title'][:30]}", callback_data=f"deal_{d['id']}")
        ])
    buttons.append([InlineKeyboardButton(text="« В меню", callback_data="back_to_menu")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("deal_"))
async def deal_card_view(callback: CallbackQuery):
    if is_duplicate(callback):
        return
    tid = callback.from_user.id
    deal_id = int(callback.data.replace("deal_", ""))
    deal = next((d for d in get_user_deals(tid) if d["id"] == deal_id), None)
    if not deal:
        await callback.answer("Сделка не найдена.")
        return

    status_labels = {
        "new": "Новая сделка", "in_progress": "В работе",
        "invoice_sent": "Счёт выставлен", "won": "Завершено", "lost": "Отказ",
    }
    text = (
        f"📋 <b>Сделка #{deal['id']}</b>\n\n"
        f"Название: {deal['title']}\n"
        f"Статус: <b>{status_labels.get(deal['status'], deal['status'])}</b>\n"
        f"Сумма: {deal['amount']:,.0f} руб"
    )
    await callback.message.edit_text(text, reply_markup=deal_card_kb(deal["id"], deal["status"]))


@router.callback_query(F.data.startswith("status_"))
async def deal_status_change(callback: CallbackQuery):
    if is_duplicate(callback):
        return
    tid = callback.from_user.id
    _, deal_id, new_status = callback.data.split("_", 2)

    status_labels = {
        "new": "Новая сделка", "in_progress": "В работе",
        "invoice_sent": "Счёт выставлен", "won": "Завершено", "lost": "Отказ",
    }

    deal = next((d for d in get_user_deals(tid) if d["id"] == int(deal_id)), None)
    if not deal:
        await callback.answer("Сделка не найдена.")
        return

    deal["status"] = new_status
    await callback.answer(f"Статус изменён на: {status_labels.get(new_status, new_status)}")
    text = (
        f"📋 <b>Сделка #{deal['id']}</b>\n\n"
        f"Название: {deal['title']}\n"
        f"Статус: <b>{status_labels.get(deal['status'], deal['status'])}</b>\n"
        f"Сумма: {deal['amount']:,.0f} руб"
    )
    await callback.message.edit_text(text, reply_markup=deal_card_kb(deal["id"], deal["status"]))


@router.callback_query(F.data.startswith("delete_"))
async def deal_delete(callback: CallbackQuery):
    if is_duplicate(callback):
        return
    tid = callback.from_user.id
    deal_id = int(callback.data.replace("delete_", ""))
    user_deals = get_user_deals(tid)
    deal = next((d for d in user_deals if d["id"] == deal_id), None)
    if deal:
        user_deals.remove(deal)
    await callback.answer("Сделка удалена.")
    await callback.message.edit_text("🗑 Сделка удалена.", reply_markup=back_kb())


# ── /clients ──
@router.callback_query(F.data == "menu_clients")
async def menu_clients(callback: CallbackQuery):
    if is_duplicate(callback):
        return
    await callback.message.edit_text(
        "👥 Клиенты создаются автоматически из входящих сообщений.\n\n"
        "Пока клиентов нет. Эта функция будет доступна в следующей версии.",
        reply_markup=back_kb(),
    )


# ── /settings ──
@router.callback_query(F.data == "menu_settings")
async def menu_settings(callback: CallbackQuery):
    if is_duplicate(callback):
        return
    tid = callback.from_user.id
    data = user_state.get(tid, {})
    deal_count = count_user_deals(tid)
    text = (
        f"⚙️ <b>Настройки</b>\n\n"
        f"Компания: {data.get('company', '—')}\n"
        f"Тариф: {data.get('tariff', '—').upper()}\n"
        f"Сделок: {deal_count}/{MAX_DEALS_PER_USER}\n\n"
        f"⚠️ <i>Тестовая MVP-версия. Данные в памяти, возможна потеря при перезапуске.</i>"
    )
    await callback.message.edit_text(text, reply_markup=back_kb())


# ── Меню ──
@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    if is_duplicate(callback):
        return
    tid = callback.from_user.id
    company = user_state.get(tid, {}).get("company", "—")
    await callback.message.edit_text(
        f"🏢 {company}\nВыберите действие:",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("invite"))
async def cmd_invite(message: Message):
    if is_duplicate(message):
        return
    tid = message.from_user.id
    if tid not in user_state or not user_state[tid].get("company"):
        await message.answer("❌ Сначала зарегистрируйтесь: /start")
        return

    import uuid
    code = str(uuid.uuid4())[:6].upper()
    await message.answer(
        f"🔗 <b>Код приглашения:</b> <code>{code}</code>\n\n"
        f"Менеджер должен перейти в @LEADYCRM_bot и нажать /start.\n\n"
        f"<i>⚠️ Проверка кода будет доступна в следующей версии.</i>",
        reply_markup=back_kb(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    if is_duplicate(message):
        return
    await message.answer(
        "📋 <b>Доступные команды:</b>\n\n"
        "/new — Создать сделку\n"
        "/deals — Список сделок\n"
        "/clients — Клиенты\n"
        "/settings — Настройки\n"
        "/invite — Пригласить менеджера\n"
        "/help — Это сообщение\n"
        "/statuses — Статусы сделок\n"
        "/pricing — Тарифы и цены\n"
        "/demo — Как это работает\n"
        "/revoke_consent — Отозвать согласие ПД\n"
        "/delete_account — Удалить аккаунт\n\n"
        f"Лимит сделок: {MAX_DEALS_PER_USER}.\n"
        "⚠️ Тестовая MVP-версия. Данные в памяти.",
        reply_markup=back_kb(),
    )


@router.message(Command("pricing"))
async def cmd_pricing(message: Message):
    if is_duplicate(message):
        return
    await message.answer(
        "💳 <b>Тарифы Leady</b>\n\n"
        "<b>Базовый — 999 руб/мес</b>\n"
        "• 1 менеджер • Сделки со статусами\n"
        "• Контакты клиентов • До 30 лидов/мес\n"
        "• 1 неделя бесплатно\n\n"
        "<b>Pro — 2 999 руб/мес</b>\n"
        "• 10 менеджеров • Кастомные статусы\n"
        "• Встроенная оплата YooKassa\n"
        "• Скидка 20% на первый месяц\n\n"
        "<b>💎 Квартал (3 мес, –10%):</b>\n"
        "• Базовый: 2 697 руб (899 руб/мес)\n"
        "• Pro: 8 097 руб (2 699 руб/мес)\n\n"
        "<b>Ultra — по запросу</b>\n"
        "• Свой бот, веб-кабинет, без лимитов\n\n"
        "<i>Без контрактов. Оплата через YooKassa с чеком (54-ФЗ).</i>",
        reply_markup=back_kb(),
    )


@router.message(Command("demo"))
async def cmd_demo(message: Message):
    if is_duplicate(message):
        return
    await message.answer(
        "📋 <b>Демо: как работает Leady</b>\n\n"
        "<b>1.</b> Регистрация компании — 1 минута\n"
        "<b>2.</b> Создание сделки: /new → название → сумма\n"
        "<b>3.</b> Статусы: Новая → В работе → Счёт → Завершено\n"
        "<b>4.</b> Приглашение менеджеров: /invite → код\n"
        "<b>5.</b> Клиенты — автосоздание из входящих\n\n"
        "<b>Сценарий за 2 минуты:</b>\n"
        "Клиент пишет в Telegram → контакт → сделка →\n"
        "смена статуса → владелец видит воронку.\n\n"
        "<i>Всё в Telegram. Ничего устанавливать не надо.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Попробовать бесплатно", callback_data="start_onboarding")],
        ]),
    )


@router.message(Command("statuses"))
async def cmd_statuses(message: Message):
    if is_duplicate(message):
        return
    await message.answer(
        "📋 <b>Статусы сделок:</b>\n\n"
        "<b>1. Новая сделка</b> — заявка только что поступила\n"
        "→ Связаться с клиентом в течение 15 минут\n\n"
        "<b>2. В работе</b> — менеджер связался, идёт обсуждение\n"
        "→ Подготовить КП, согласовать детали\n\n"
        "<b>3. Счёт выставлен</b> — КП отправлено, ожидается оплата\n"
        "→ Напомнить клиенту через 1-2 дня\n\n"
        "<b>4. Завершено</b> — клиент оплатил, сделка закрыта\n"
        "→ Передать клиента на сопровождение\n\n"
        "<b>5. Отказ</b> — клиент отказался, сделка без результата\n"
        "→ Записать причину отказа",
        reply_markup=back_kb(),
    )


@router.message(Command("revoke_consent"))
async def cmd_revoke(message: Message):
    if is_duplicate(message):
        return
    await message.answer(
        "⚠️ <b>Согласие на обработку ПД отозвано.</b>\n\n"
        "Обработка будущих данных прекращена. "
        "Исторические данные сохранятся 90 дней (152-ФЗ ст.9 ч.2)."
    )


@router.message(Command("delete_account"))
async def cmd_delete(message: Message):
    if is_duplicate(message):
        return
    await message.answer(
        "⚠️ <b>Удаление аккаунта</b>\n\n"
        "Полное удаление возможно после окончания подписки. "
        "Данные хранятся 90 дней."
    )


@router.message()
async def fallback(message: Message):
    if is_duplicate(message):
        return
    await message.answer("Используйте меню или /help.", reply_markup=main_menu_kb())


async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Leady MVP Bot запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
