from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_menu(
    can_edit: bool,
    can_cancel_draw: bool = False,
    can_create_game: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Учасники", callback_data="admin:participants")
    if can_edit:
        builder.button(text="Додати учасника", callback_data="admin:add")
        builder.button(text="Заборонені пари", callback_data="admin:pairs")
        builder.button(text="Перевірити жеребкування", callback_data="admin:draw")
    if can_cancel_draw:
        builder.button(text="Скасувати жеребкування", callback_data="admin:cancel_draw")
    if can_create_game:
        builder.button(text="Нова гра", callback_data="admin:new_game")
    builder.button(text="Повторити невдалі повідомлення", callback_data="admin:retry")
    builder.adjust(1)
    return builder.as_markup()
