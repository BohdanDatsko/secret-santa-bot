from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models.game import Game
from app.database.models.user import User
from app.services.common import require_organizer
from app.services.errors import InvalidStateError, NotFoundError, PermissionDeniedError


class GameService:
    async def ensure_initial_game(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
    ) -> Game:
        if actor_telegram_id != settings.admin_telegram_id:
            raise PermissionDeniedError("Лише організатор може підготувати гру.")
        async with session.begin():
            organizer = await session.scalar(
                select(User).where(User.telegram_id == actor_telegram_id).with_for_update()
            )
            if organizer is None:
                raise NotFoundError("Спочатку надішліть /start.")
            game = await session.scalar(
                select(Game).order_by(Game.id.desc()).limit(1).with_for_update()
            )
            if game is None:
                game = Game(name="Секретний Миколай", organizer_id=organizer.id)
                session.add(game)
                await session.flush()
            elif game.organizer_id != organizer.id:
                raise PermissionDeniedError("Ви не є організатором поточної гри.")
            return game

    async def current_game(self, session: AsyncSession) -> Game:
        async with session.begin():
            game = await session.scalar(select(Game).order_by(Game.id.desc()).limit(1))
            if game is None:
                raise NotFoundError("Гру ще не створено. Організатор має надіслати /start.")
            return game

    async def create_game(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        name: str,
    ) -> Game:
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 120:
            raise InvalidStateError("Назва гри має містити від 1 до 120 символів.")
        if actor_telegram_id != settings.admin_telegram_id:
            raise PermissionDeniedError("Лише організатор може створити гру.")
        async with session.begin():
            organizer = await session.scalar(
                select(User).where(User.telegram_id == actor_telegram_id).with_for_update()
            )
            if organizer is None:
                raise NotFoundError("Спочатку надішліть /start.")
            current_game = await session.scalar(
                select(Game).order_by(Game.id.desc()).limit(1).with_for_update()
            )
            if current_game is not None and current_game.status == "SETUP":
                raise InvalidStateError("Спочатку завершіть жеребкування або скасуйте поточну гру.")
            game = Game(name=clean_name, organizer_id=organizer.id)
            session.add(game)
            await session.flush()
            return game

    async def cancel_game(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        game_id: int,
    ) -> None:
        async with session.begin():
            game = await session.scalar(select(Game).where(Game.id == game_id).with_for_update())
            if game is None:
                raise NotFoundError("Гру не знайдено.")
            await require_organizer(session, settings, game, actor_telegram_id)
            if game.status != "SETUP":
                raise InvalidStateError("Скасувати можна лише гру у статусі SETUP.")
            game.status = "CANCELLED"
