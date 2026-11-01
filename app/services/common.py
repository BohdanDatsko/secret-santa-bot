from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models.game import Game
from app.database.models.user import User
from app.services.errors import NotFoundError, PermissionDeniedError


async def require_organizer(
    session: AsyncSession,
    settings: Settings,
    game: Game,
    actor_telegram_id: int,
) -> User:
    if actor_telegram_id != settings.admin_telegram_id:
        raise PermissionDeniedError("Ця дія доступна лише організатору.")
    user = await session.scalar(select(User).where(User.telegram_id == actor_telegram_id))
    if user is None:
        raise NotFoundError("Спочатку надішліть /start.")
    if user.id != game.organizer_id:
        raise PermissionDeniedError("Ви не є організатором цієї гри.")
    return user


async def get_game(session: AsyncSession, game_id: int) -> Game:
    game = await session.get(Game, game_id)
    if game is None:
        raise NotFoundError("Гру не знайдено.")
    return game


async def get_game_for_update(session: AsyncSession, game_id: int) -> Game:
    game = await session.scalar(select(Game).where(Game.id == game_id).with_for_update())
    if game is None:
        raise NotFoundError("Гру не знайдено.")
    return game
