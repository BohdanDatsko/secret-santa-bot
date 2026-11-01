from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models.participant import Participant
from app.database.models.user import User
from app.services.common import get_game, get_game_for_update, require_organizer
from app.services.errors import ConflictError, InvalidStateError, NotFoundError


class ParticipantService:
    async def candidates(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        game_id: int,
    ) -> list[User]:
        game = await get_game(session, game_id)
        await require_organizer(session, settings, game, actor_telegram_id)
        registered = select(Participant.user_id).where(Participant.game_id == game_id)
        result = await session.scalars(
            select(User).where(User.id.not_in(registered)).order_by(User.first_name, User.id)
        )
        return list(result)

    async def list_participants(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        game_id: int,
    ) -> list[Participant]:
        game = await get_game(session, game_id)
        await require_organizer(session, settings, game, actor_telegram_id)
        result = await session.scalars(
            select(Participant).where(Participant.game_id == game_id).order_by(Participant.id)
        )
        return list(result)

    async def add(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        game_id: int,
        user_id: int,
    ) -> Participant:
        async with session.begin():
            game = await get_game_for_update(session, game_id)
            await require_organizer(session, settings, game, actor_telegram_id)
            if game.status != "SETUP":
                raise InvalidStateError("Учасників можна змінювати лише у статусі SETUP.")
            user = await session.get(User, user_id)
            if user is None:
                raise NotFoundError("Користувача не знайдено.")
            existing = await session.scalar(
                select(Participant).where(
                    Participant.game_id == game_id,
                    Participant.user_id == user_id,
                )
            )
            if existing is not None:
                raise ConflictError("Цей користувач уже бере участь у грі.")
            participant = Participant(
                game_id=game_id,
                user_id=user.id,
                display_name=user.first_name,
            )
            session.add(participant)
            await session.flush()
            return participant

    async def remove(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        game_id: int,
        participant_id: int,
    ) -> None:
        async with session.begin():
            game = await get_game_for_update(session, game_id)
            await require_organizer(session, settings, game, actor_telegram_id)
            if game.status != "SETUP":
                raise InvalidStateError("Учасників можна змінювати лише у статусі SETUP.")
            participant = await session.scalar(
                select(Participant).where(
                    Participant.id == participant_id,
                    Participant.game_id == game_id,
                )
            )
            if participant is None:
                raise NotFoundError("Учасника не знайдено.")
            await session.delete(participant)
