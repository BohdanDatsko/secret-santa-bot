from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models.exclusion import Exclusion
from app.database.models.participant import Participant
from app.services.common import get_game, get_game_for_update, require_organizer
from app.services.errors import ConflictError, InvalidStateError, NotFoundError


class ExclusionService:
    async def list_pairs(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        game_id: int,
    ) -> list[Exclusion]:
        game = await get_game(session, game_id)
        await require_organizer(session, settings, game, actor_telegram_id)
        result = await session.scalars(
            select(Exclusion)
            .where(Exclusion.game_id == game_id)
            .order_by(Exclusion.participant_a_id, Exclusion.participant_b_id)
        )
        return list(result)

    async def add_pair(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        game_id: int,
        first_id: int,
        second_id: int,
    ) -> Exclusion:
        if first_id == second_id:
            raise InvalidStateError("Не можна заборонити учасника самому собі.")
        first_id, second_id = sorted((first_id, second_id))
        async with session.begin():
            game = await get_game_for_update(session, game_id)
            await require_organizer(session, settings, game, actor_telegram_id)
            if game.status != "SETUP":
                raise InvalidStateError("Пари можна змінювати лише у статусі SETUP.")
            participants = await session.scalars(
                select(Participant.id).where(
                    Participant.game_id == game_id,
                    Participant.id.in_((first_id, second_id)),
                    Participant.is_active.is_(True),
                )
            )
            if set(participants) != {first_id, second_id}:
                raise NotFoundError("Обидва учасники мають належати цій грі.")
            existing = await session.scalar(
                select(Exclusion).where(
                    Exclusion.game_id == game_id,
                    Exclusion.participant_a_id == first_id,
                    Exclusion.participant_b_id == second_id,
                )
            )
            if existing is not None:
                raise ConflictError("Ця заборонена пара вже існує.")
            pair = Exclusion(
                game_id=game_id,
                participant_a_id=first_id,
                participant_b_id=second_id,
            )
            session.add(pair)
            await session.flush()
            return pair

    async def remove_pair(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        game_id: int,
        exclusion_id: int,
    ) -> None:
        async with session.begin():
            game = await get_game_for_update(session, game_id)
            await require_organizer(session, settings, game, actor_telegram_id)
            if game.status != "SETUP":
                raise InvalidStateError("Пари можна змінювати лише у статусі SETUP.")
            pair = await session.scalar(
                select(Exclusion).where(
                    Exclusion.id == exclusion_id,
                    Exclusion.game_id == game_id,
                )
            )
            if pair is None:
                raise NotFoundError("Заборонену пару не знайдено.")
            await session.delete(pair)
