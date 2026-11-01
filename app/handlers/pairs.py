from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.handlers.admin import _authorized_game
from app.keyboards.pairs import exclusion_keyboard
from app.keyboards.participants import participant_picker
from app.services.exclusion_service import ExclusionService
from app.services.participant_service import ParticipantService
from app.states.exclusion import ExclusionStates

router = Router(name="pairs")


@router.callback_query(F.data == "admin:pairs")
async def show_pairs(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    service = ExclusionService()
    pairs = await service.list_pairs(session, settings, callback.from_user.id, game.id)
    participants = await ParticipantService().list_participants(
        session, settings, callback.from_user.id, game.id
    )
    await callback.message.answer(
        "Заборонених пар поки немає." if not pairs else "Заборонені пари:",
        reply_markup=exclusion_keyboard(pairs, participants, game.status == "SETUP"),
    )
    await callback.answer()


@router.callback_query(F.data == "pair:add")
async def begin_pair(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    if game.status != "SETUP":
        await callback.answer("Гра вже не приймає змін.", show_alert=True)
        return
    participants = await ParticipantService().list_participants(
        session, settings, callback.from_user.id, game.id
    )
    if len(participants) < 2:
        await callback.answer("Для забороненої пари потрібні двоє учасників.", show_alert=True)
        return
    await state.set_state(ExclusionStates.waiting_for_first)
    await callback.message.answer(
        "Оберіть першого учасника:",
        reply_markup=participant_picker(participants, "pair:first"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pair:first:"), ExclusionStates.waiting_for_first)
async def choose_first(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    first_id = int(callback.data.rsplit(":", 1)[1])
    participants = await ParticipantService().list_participants(
        session, settings, callback.from_user.id, game.id
    )
    if first_id not in {participant.id for participant in participants}:
        await callback.answer("Учасника більше немає в цій грі.", show_alert=True)
        await state.clear()
        return
    await state.update_data(first_id=first_id)
    await state.set_state(ExclusionStates.waiting_for_second)
    remaining = [participant for participant in participants if participant.id != first_id]
    await callback.message.answer(
        "Оберіть другого учасника:",
        reply_markup=participant_picker(remaining, "pair:second"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pair:second:"), ExclusionStates.waiting_for_second)
async def choose_second(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    data = await state.get_data()
    first_id = data.get("first_id")
    second_id = int(callback.data.rsplit(":", 1)[1])
    await ExclusionService().add_pair(
        session, settings, callback.from_user.id, game.id, first_id, second_id
    )
    await state.clear()
    await callback.message.answer("Заборонену пару збережено.")
    await callback.answer()


@router.callback_query(F.data.startswith("pair:remove:"))
async def remove_pair(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    exclusion_id = int(callback.data.rsplit(":", 1)[1])
    await ExclusionService().remove_pair(
        session, settings, callback.from_user.id, game.id, exclusion_id
    )
    await callback.answer("Пару видалено.")
    await callback.message.answer("Заборонену пару видалено.")
