from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models.exclusion import Exclusion
from app.database.models.participant import Participant


def exclusion_keyboard(
    exclusions: list[Exclusion],
    participants: list[Participant],
    can_edit: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_edit:
        names = {participant.id: participant.display_name for participant in participants}
        for pair in exclusions:
            label = (
                f"Видалити: {names.get(pair.participant_a_id, '?')} ↔ "
                f"{names.get(pair.participant_b_id, '?')}"
            )
            builder.button(
                text=label[:64],
                callback_data=f"pair:remove:{pair.id}",
            )
        builder.button(text="Додати заборонену пару", callback_data="pair:add")
        builder.adjust(1)
    return builder.as_markup()
