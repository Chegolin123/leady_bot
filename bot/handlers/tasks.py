import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from bot.api_client import api
from bot.keyboards.inline import back_to_menu_kb

logger = logging.getLogger(__name__)
router = Router()


class NewTask(StatesGroup):
    waiting_title = State()
    waiting_due = State()


@router.message(Command("tasks"))
async def cmd_tasks(message: Message, user: dict = None):
    if not user:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return

    try:
        tasks_list = await api.list_tasks(str(user["tenant_id"]))
        if not tasks_list:
            await message.answer("📋 У вас пока нет задач.\n/newtask — создать.", reply_markup=back_to_menu_kb())
            return

        text = "📋 <b>Задачи:</b>\n\n"
        for t in tasks_list:
            emoji = {"todo": "⬜", "in_progress": "🔄", "done": "✅"}.get(t["status"], "⬜")
            due = f" | 📅 {t['due_at'][:10]}" if t.get("due_at") else ""
            text += f"{emoji} {t['title']}{due}\n"
            text += f"   /done_{t['id'][:8]} — отметить выполненной\n"

        await message.answer(text, reply_markup=back_to_menu_kb())
    except Exception as e:
        logger.error(f"Tasks error: {e}")
        await message.answer("❌ Задачи доступны на тарифе Pro.")


@router.message(Command("newtask"))
async def cmd_new_task(message: Message, state: FSMContext, user: dict = None):
    if not user:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return

    await message.answer("Введите название задачи:")
    await state.set_state(NewTask.waiting_title)


@router.message(NewTask.waiting_title)
async def task_title_entered(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Дедлайн (в формате ГГГГ-ММ-ДД) или /skip:")
    await state.set_state(NewTask.waiting_due)


@router.message(NewTask.waiting_due)
async def task_due_entered(message: Message, state: FSMContext, user: dict = None):
    data = await state.get_data()
    due = message.text.strip() if message.text != "/skip" else None
    await state.clear()

    try:
        task = await api.create_task(
            str(user["tenant_id"]),
            data["title"],
            description=None,
            due_at=due,
        )
        await message.answer(f"✅ Задача создана: {task['title']}", reply_markup=back_to_menu_kb())
    except Exception as e:
        logger.error(f"Task creation error: {e}")
        await message.answer("❌ Ошибка создания задачи.")


@router.message(F.text.startswith("/done_"))
async def cmd_done_task(message: Message, user: dict = None):
    if not user:
        return

    task_id_prefix = message.text[6:].strip()
    try:
        tasks_list = await api.list_tasks(str(user["tenant_id"]))
        for t in tasks_list:
            if t["id"].startswith(task_id_prefix):
                await api.update_task(str(user["tenant_id"]), t["id"], {"status": "done"})
                await message.answer(f"✅ Задача выполнена: {t['title']}", reply_markup=back_to_menu_kb())
                return
        await message.answer("❌ Задача не найдена.")
    except Exception as e:
        logger.error(f"Done task error: {e}")
        await message.answer("❌ Ошибка.")
