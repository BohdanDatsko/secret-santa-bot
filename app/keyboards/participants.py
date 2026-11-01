from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models.participant import Participant
from app.database.models.user import User


def candidates_keyboard(candidates: list[User]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in candidates:
        label = user.first_name
        if user.username:
            label += f" (@{user.username})"
        builder.button(text=label[:64], callback_data=f"participant:add:{user.id}")
    builder.adjust(1)
    return builder.as_markup()


def participants_keyboard(
    participants: list[Participant],
    can_remove: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_remove:
        for participant in participants:
            builder.button(
                text=f"Видалити: {participant.display_name}"[:64],
                callback_data=f"participant:remove:{participant.id}",
            )
        builder.adjust(1)
    return builder.as_markup()


def participant_picker(
    participants: list[Participant],
    callback_prefix: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for participant in participants:
        builder.button(
            text=participant.display_name[:64],
            callback_data=f"{callback_prefix}:{participant.id}",
        )
    builder.adjust(1)
    return builder.as_markup()
