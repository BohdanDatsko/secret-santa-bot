import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models.game import Game
from app.keyboards.admin import admin_menu
from app.keyboards.participants import candidates_keyboard, participants_keyboard
from app.services.common import require_organizer
from app.services.errors import PermissionDeniedError
from app.services.game_service import GameService
from app.services.outbox_service import OutboxService
from app.services.participant_service import ParticipantService
from app.states.game import GameStates

router = Router(name="admin")


async def _authorized_game(
    session: AsyncSession,
    settings: Settings,
    telegram_id: int,
) -> Game:
    if telegram_id != settings.admin_telegram_id:
        raise PermissionDeniedError("Ця дія доступна лише організатору.")
    game = await GameService().current_game(session)
    await require_organizer(session, settings, game, telegram_id)
    await session.commit()
    return game


@router.message(Command("admin"))
async def show_admin(
    message: Message,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, message.from_user.id)
    await message.answer(
        f"Гра «{html.escape(game.name)}» — статус <b>{game.status}</b>.",
        reply_markup=admin_menu(
            can_edit=game.status == "SETUP",
            can_cancel_draw=game.status == "DRAWN",
            can_create_game=game.status != "SETUP",
        ),
    )


@router.message(Command("new_game"))
async def new_game(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not command.args:
        await _authorized_game(session, settings, message.from_user.id)
        await state.set_state(GameStates.waiting_for_name)
        await message.answer(
            "Надішліть назву нової гри (від 1 до 120 символів). "
            "Щоб скасувати, надішліть /cancel."
        )
        return
    game = await GameService().create_game(
        session, settings, message.from_user.id, command.args
    )
    await state.clear()
    await message.answer(
        f"Створено гру «{html.escape(game.name)}» у статусі SETUP.",
        reply_markup=admin_menu(can_edit=True),
    )


@router.callback_query(F.data == "admin:new_game")
async def begin_new_game(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    if game.status == "SETUP":
        await callback.answer("Спочатку завершіть або скасуйте поточну гру.", show_alert=True)
        return
    await state.set_state(GameStates.waiting_for_name)
    await callback.message.answer(
        "Надішліть назву нової гри (від 1 до 120 символів). "
        "Щоб скасувати, надішліть /cancel."
    )
    await callback.answer()


@router.message(GameStates.waiting_for_name, F.text)
async def create_game_from_name(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    state: FSMContext,
) -> None:
    game = await GameService().create_game(
        session, settings, message.from_user.id, message.text
    )
    await state.clear()
    await message.answer(
        f"Створено гру «{html.escape(game.name)}» у статусі SETUP.",
        reply_markup=admin_menu(can_edit=True),
    )


@router.message(Command("cancel_game"))
async def cancel_game(
    message: Message,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await GameService().current_game(session)
    await GameService().cancel_game(session, settings, message.from_user.id, game.id)
    await message.answer("Гру скасовано. Щоб почати нову, використайте /new_game назва.")


@router.message(Command("retry_notifications"))
async def retry_notifications(
    message: Message,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, message.from_user.id)
    count = await OutboxService().retry_pending(session, settings, message.from_user.id, game.id)
    await message.answer(f"Повторну доставку заплановано для повідомлень: {count}.")


@router.callback_query(F.data == "admin:participants")
async def show_participants(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    participants = await ParticipantService().list_participants(
        session, settings, callback.from_user.id, game.id
    )
    text = (
        "Учасників поки немає."
        if not participants
        else (
            "Учасники:\n"
            + "\n".join(f"• {html.escape(item.display_name)}" for item in participants)
        )
    )
    await callback.message.answer(
        text,
        reply_markup=participants_keyboard(participants, game.status == "SETUP"),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:add")
async def show_candidates(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    candidates = await ParticipantService().candidates(
        session, settings, callback.from_user.id, game.id
    )
    if game.status != "SETUP":
        await callback.answer("Гра вже не приймає змін.", show_alert=True)
        return
    await callback.message.answer(
        "Оберіть зареєстрованого користувача для додавання:"
        if candidates
        else "Немає зареєстрованих користувачів для додавання.",
        reply_markup=candidates_keyboard(candidates),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:retry")
async def retry_from_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    count = await OutboxService().retry_pending(session, settings, callback.from_user.id, game.id)
    await callback.answer(f"Заплановано: {count}", show_alert=True)
