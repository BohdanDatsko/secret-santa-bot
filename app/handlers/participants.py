from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.handlers.admin import _authorized_game
from app.services.participant_service import ParticipantService

router = Router(name="participants")


@router.callback_query(F.data.startswith("participant:add:"))
async def add_participant(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    user_id = int(callback.data.rsplit(":", 1)[1])
    await ParticipantService().add(session, settings, callback.from_user.id, game.id, user_id)
    await callback.answer("Учасника додано.")
    await callback.message.answer("Учасника додано до гри.")


@router.callback_query(F.data.startswith("participant:remove:"))
async def remove_participant(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    participant_id = int(callback.data.rsplit(":", 1)[1])
    await ParticipantService().remove(
        session, settings, callback.from_user.id, game.id, participant_id
    )
    await callback.answer("Учасника видалено.")
    await callback.message.answer("Учасника видалено з гри.")
