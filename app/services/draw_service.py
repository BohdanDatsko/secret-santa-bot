import random
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models.assignment import Assignment
from app.database.models.exclusion import Exclusion
from app.database.models.game import Game
from app.database.models.notification_outbox import NotificationOutbox
from app.database.models.participant import Participant
from app.domain.draw_algorithm import find_assignment
from app.services.common import require_organizer
from app.services.errors import ConflictError, InvalidStateError, NoAssignmentError, NotFoundError


class DrawService:
    async def preview(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        game_id: int,
    ) -> tuple[int, bool]:
        game = await session.get(Game, game_id)
        if game is None:
            raise NotFoundError("Гру не знайдено.")
        await require_organizer(session, settings, game, actor_telegram_id)
        if game.status != "SETUP":
            raise InvalidStateError("Жеребкування доступне лише у статусі SETUP.")
        participants = list(
            await session.scalars(
                select(Participant)
                .where(Participant.game_id == game_id, Participant.is_active.is_(True))
                .order_by(Participant.id)
            )
        )
        pairs = list(
            await session.execute(
                select(Exclusion.participant_a_id, Exclusion.participant_b_id).where(
                    Exclusion.game_id == game_id
                )
            )
        )
        possible = find_assignment(
            [participant.id for participant in participants],
            [(pair[0], pair[1]) for pair in pairs],
        )
        return len(participants), possible is not None

    async def draw(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        game_id: int,
        rng: random.Random | random.SystemRandom | None = None,
    ) -> int:
        async with session.begin():
            game = await session.scalar(select(Game).where(Game.id == game_id).with_for_update())
            if game is None:
                raise NotFoundError("Гру не знайдено.")
            await require_organizer(session, settings, game, actor_telegram_id)
            if game.status != "SETUP":
                raise ConflictError("Жеребкування вже виконано або гру закрито.")
            participants = list(
                await session.scalars(
                    select(Participant)
                    .where(Participant.game_id == game_id, Participant.is_active.is_(True))
                    .order_by(Participant.id)
                )
            )
            pairs = list(
                await session.execute(
                    select(Exclusion.participant_a_id, Exclusion.participant_b_id).where(
                        Exclusion.game_id == game_id
                    )
                )
            )
            assignment = find_assignment(
                [participant.id for participant in participants],
                [(pair[0], pair[1]) for pair in pairs],
                rng,
            )
            if assignment is None:
                raise NoAssignmentError(
                    "Для цих учасників і заборонених пар немає допустимого жеребкування."
                )

            records = [
                Assignment(game_id=game_id, giver_id=giver, receiver_id=receiver)
                for giver, receiver in assignment.items()
            ]
            session.add_all(records)
            await session.flush()
            session.add_all([NotificationOutbox(assignment_id=record.id) for record in records])
            game.status = "DRAWN"
            game.drawn_at = datetime.now(UTC)
            return len(records)
