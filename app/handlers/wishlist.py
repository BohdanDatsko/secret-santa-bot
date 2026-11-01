import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.game import Game
from app.services.game_service import GameService
from app.services.wishlist_service import WishlistService
from app.states.wishlist import WishlistStates

router = Router(name="wishlist")


async def _current_game(session: AsyncSession) -> Game:
    return await GameService().current_game(session)


@router.message(Command("wishlist"))
async def edit_wishlist(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    game = await _current_game(session)
    if command.args:
        await WishlistService().update(session, message.from_user.id, game.id, command.args)
        await message.answer("Wishlist збережено.")
        return
    await state.set_state(WishlistStates.waiting_for_text)
    await message.answer("Надішліть wishlist одним повідомленням (до 2000 символів).")


@router.message(WishlistStates.waiting_for_text, F.text)
async def save_wishlist(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    game = await _current_game(session)
    await WishlistService().update(session, message.from_user.id, game.id, message.text)
    await state.clear()
    await message.answer("Wishlist збережено.")


@router.message(Command("gift"))
async def show_gift(
    message: Message,
    session: AsyncSession,
) -> None:
    game = await _current_game(session)
    recipient_name, wishlist = await WishlistService().recipient_wishlist(
        session, message.from_user.id, game.id
    )
    await message.answer(
        f"Ви даруєте подарунок: <b>{html.escape(recipient_name)}</b>\n\n"
        f"<b>Wishlist:</b>\n{html.escape(wishlist or 'Wishlist не вказано.')}"
    )
