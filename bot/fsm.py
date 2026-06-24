from aiogram.fsm.state import State, StatesGroup


class OnboardingState(StatesGroup):
    waiting_tariff = State()
    waiting_period = State()
    waiting_company_name = State()
    waiting_payment = State()
    waiting_bot_name = State()
    waiting_bot_username = State()
    waiting_bot_token = State()


class TicketState(StatesGroup):
    waiting_title = State()
    waiting_text = State()
    waiting_reply = State()
