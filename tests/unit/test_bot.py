from app.bot import create_dispatcher
from app.keyboards.admin import admin_menu


def test_dispatcher_receives_settings_dependency(session_factory, settings) -> None:
    dispatcher = create_dispatcher(session_factory, settings)

    assert dispatcher["settings"] is settings


def test_admin_menu_shows_new_game_button_when_allowed() -> None:
    menu = admin_menu(can_edit=False, can_create_game=True)

    assert any(
        button.callback_data == "admin:new_game"
        for row in menu.inline_keyboard
        for button in row
    )
