from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.handlers.admin import _authorized_game
from app.keyboards.admin import admin_menu
from app.services.draw_service import DrawService

router = Router(name="draw")


@router.callback_query(F.data == "admin:draw")
async def preview_draw(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    count, possible = await DrawService().preview(session, settings, callback.from_user.id, game.id)
    if not possible:
        await callback.message.answer(
            f"Повне жеребкування неможливе для {count} учасників із поточними "
            "обмеженнями. Результати не змінено."
        )
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="Підтвердити жеребкування", callback_data="draw:confirm")
    await callback.message.answer(
        f"Знайдено допустиме жеребкування для {count} учасників. "
        "Після підтвердження результати буде зафіксовано.",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "draw:confirm")
async def confirm_draw(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    count = await DrawService().draw(session, settings, callback.from_user.id, game.id)
    await callback.message.answer(
        f"Жеребкування завершено для {count} учасників. "
        "Результати записано; доставка повідомлень триває окремо."
    )
    await callback.answer("Результати зафіксовано.")


@router.callback_query(F.data == "admin:cancel_draw")
async def cancel_draw(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    game = await _authorized_game(session, settings, callback.from_user.id)
    await DrawService().cancel_draw(session, settings, callback.from_user.id, game.id)
    await callback.message.answer(
        "Жеребкування скасовано до початку доставки. "
        "Гра знову у статусі SETUP — можна сформувати новий результат.",
        reply_markup=admin_menu(can_edit=True),
    )
    await callback.answer("Жеребкування скасовано.")
