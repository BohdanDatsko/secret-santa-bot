import html

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.keyboards.admin import admin_menu
from app.services.game_service import GameService
from app.services.user_service import UserService

router = Router(name="start")


@router.message(CommandStart())
async def start(
    message: Message,
    session: AsyncSession,
    settings: Settings,
) -> None:
    user = await UserService().register(
        session,
        message.from_user.id,
        message.from_user.first_name,
        message.from_user.username,
    )
    if message.from_user.id == settings.admin_telegram_id:
        game = await GameService().ensure_initial_game(session, settings, message.from_user.id)
        await message.answer(
            f"Вітаю, організаторе! Поточна гра: <b>{html.escape(game.name)}</b> "
            f"({game.status}).\n"
            "Щоб створити нову гру, використайте /new_game назва.",
            reply_markup=admin_menu(
                can_edit=game.status == "SETUP",
                can_cancel_draw=game.status == "DRAWN",
                can_create_game=game.status != "SETUP",
            ),
        )
        return
    await message.answer(
        f"Вітаю, {html.escape(user.first_name)}! Ви зареєстровані в боті, "
        "але ще не додані до гри "
        "організатором.\n"
        "Після жеребкування використайте /gift, щоб переглянути wishlist отримувача, "
        "або /wishlist для редагування власного списку."
    )


@router.message(Command("cancel"))
async def cancel_fsm(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Введення скасовано.")
