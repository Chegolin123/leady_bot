from aiogram.types import InlineKeyboardMarkup


def _btn(text: str, callback_data: str) -> dict:
    return {"text": text, "callback_data": callback_data}


# ══════════════════════════════════════════════════════════════════════
# ADMIN (ты) — 7 кнопок
# ══════════════════════════════════════════════════════════════════════

def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("\U0001f3e2 Компании", "admin_companies")],
            [_btn("\U0001f465 Пользователи", "admin_users")],
            [_btn("\U0001f916 Боты", "admin_bots")],
            [_btn("\U0001f4ac Тикеты", "admin_tickets")],
            [_btn("\U0001f4ca Статистика", "admin_stats")],
            [_btn("\U0001f4cb Логи", "admin_logs")],
        ]
    )


# ══════════════════════════════════════════════════════════════════════
# PLATFORM MANAGER (саппорт) — 4 кнопки
# ══════════════════════════════════════════════════════════════════════

def manager_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("\U0001f4ac Тикеты", "manager_tickets")],
            [_btn("\U0001f3e2 Компании", "manager_companies")],
            [_btn("\U0001f4ca Статистика", "manager_stats")],
            [_btn("\u2753 Помощь", "manager_help")],
        ]
    )


# ══════════════════════════════════════════════════════════════════════
# CLIENT (купил подписку) — мини-меню
# ══════════════════════════════════════════════════════════════════════

def client_menu(bot_username: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("\U0001f4cb Моя подписка", "client_subscription")],
    ])
    if bot_username:
        kb.inline_keyboard.insert(0, [
            {"text": f"\U0001f916 Перейти в @{bot_username}", "url": f"https://t.me/{bot_username}"}
        ])
    return kb


# ══════════════════════════════════════════════════════════════════════
# ONBOARDING
# ══════════════════════════════════════════════════════════════════════

def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("\u2705 Принимаю", "consent_accept")],
            [_btn("\u274c Отказываюсь", "consent_decline")],
        ]
    )


def onboarding_tariff_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("BASIC", "tariff_base")],
            [_btn("PRO", "tariff_pro")],
        ]
    )


def onboarding_period_keyboard(tariff: str) -> InlineKeyboardMarkup:
    prices = {"base": ("1 месяц — 999 \u20bd", 999), "pro": ("1 месяц — 2 999 \u20bd", 2999)}
    quarter = {"base": ("3 месяца — 2 697 \u20bd", 2697), "pro": ("3 месяца — 8 097 \u20bd", 8097)}
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(prices[tariff][0], f"period_{tariff}_1")],
            [_btn(quarter[tariff][0], f"period_{tariff}_3")],
            [_btn("\u2190 Назад к тарифам", "back_to_tariff")],
        ]
    )


# ══════════════════════════════════════════════════════════════════════
# SHARED
# ══════════════════════════════════════════════════════════════════════

def back_to_menu_btn() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn("\u2190 Назад", "back_to_menu")]]
    )
