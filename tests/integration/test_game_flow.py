import random

import pytest
from aiogram.exceptions import TelegramAPIError
from aiogram.methods import SendMessage
from sqlalchemy import func, select

from app.database.models.assignment import Assignment
from app.database.models.game import Game
from app.database.models.notification_outbox import NotificationOutbox
from app.database.models.participant import Participant
from app.database.models.user import User
from app.services.draw_service import DrawService
from app.services.errors import (
    ConflictError,
    InvalidStateError,
    NoAssignmentError,
    NotFoundError,
)
from app.services.exclusion_service import ExclusionService
from app.services.game_service import GameService
from app.services.outbox_service import OutboxService
from app.services.participant_service import ParticipantService
from app.services.user_service import UserService
from app.services.wishlist_service import WishlistService


async def create_game(session, settings):
    users = UserService()
    await users.register(session, settings.admin_telegram_id, "Organizer", None)
    game = await GameService().ensure_initial_game(session, settings, settings.admin_telegram_id)
    participant_service = ParticipantService()
    participants = []
    for telegram_id in (20001, 20002, 20003, 20004):
        user = await users.register(session, telegram_id, f"Guest {telegram_id}", None)
        participants.append(
            await participant_service.add(
                session,
                settings,
                settings.admin_telegram_id,
                game.id,
                user.id,
            )
        )
    return game, participants


@pytest.mark.asyncio
async def test_draw_commits_once_and_creates_outbox(session_factory, settings) -> None:
    async with session_factory() as session:
        game, participants = await create_game(session, settings)
        game_id = game.id
        excluded_pair = {participants[0].id, participants[1].id}
        await ExclusionService().add_pair(
            session,
            settings,
            settings.admin_telegram_id,
            game.id,
            participants[0].id,
            participants[1].id,
        )
        count = await DrawService().draw(
            session,
            settings,
            settings.admin_telegram_id,
            game.id,
            random.Random(7),
        )
        assert count == len(participants)
        with pytest.raises(ConflictError):
            await DrawService().draw(session, settings, settings.admin_telegram_id, game.id)

        assignments = list(
            await session.scalars(select(Assignment).where(Assignment.game_id == game_id))
        )
        assert len(assignments) == len(participants)
        assert len({row.giver_id for row in assignments}) == len(participants)
        assert len({row.receiver_id for row in assignments}) == len(participants)
        assert all(row.giver_id != row.receiver_id for row in assignments)
        assert all({row.giver_id, row.receiver_id} != excluded_pair for row in assignments)
        assert await session.scalar(select(func.count()).select_from(NotificationOutbox)) == len(
            participants
        )
        saved_game = await session.get(Game, game_id)
        assert saved_game.status == "DRAWN"


@pytest.mark.asyncio
async def test_impossible_draw_rolls_back_without_partial_results(
    session_factory, settings
) -> None:
    async with session_factory() as session:
        game, participants = await create_game(session, settings)
        game_id = game.id
        exclusions = ExclusionService()
        for other in participants[1:]:
            await exclusions.add_pair(
                session,
                settings,
                settings.admin_telegram_id,
                game.id,
                participants[0].id,
                other.id,
            )

        with pytest.raises(NoAssignmentError):
            await DrawService().draw(
                session,
                settings,
                settings.admin_telegram_id,
                game.id,
                random.Random(3),
            )

        assert await session.scalar(select(func.count()).select_from(Assignment)) == 0
        assert await session.scalar(select(func.count()).select_from(NotificationOutbox)) == 0
        saved_game = await session.get(Game, game_id)
        assert saved_game.status == "SETUP"


@pytest.mark.asyncio
async def test_draw_can_be_cancelled_before_notification_attempts(session_factory, settings) -> None:
    async with session_factory() as session:
        game, participants = await create_game(session, settings)
        game_id = game.id
        await DrawService().draw(
            session,
            settings,
            settings.admin_telegram_id,
            game_id,
            random.Random(19),
        )

        await DrawService().cancel_draw(session, settings, settings.admin_telegram_id, game_id)
        saved_game = await session.get(Game, game_id)
        assert saved_game.status == "SETUP"
        assert saved_game.drawn_at is None
        assert await session.scalar(select(func.count()).select_from(Assignment)) == 0
        assert await session.scalar(select(func.count()).select_from(NotificationOutbox)) == 0

        await session.commit()
        assert (
            await DrawService().draw(
                session,
                settings,
                settings.admin_telegram_id,
                game_id,
                random.Random(20),
            )
            == len(participants)
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["PENDING", "DELIVERED"])
async def test_draw_cannot_be_cancelled_after_notification_attempt(
    session_factory, settings, status
) -> None:
    async with session_factory() as session:
        game, _ = await create_game(session, settings)
        game_id = game.id
        await DrawService().draw(
            session,
            settings,
            settings.admin_telegram_id,
            game_id,
            random.Random(21),
        )
        item = await session.scalar(select(NotificationOutbox).limit(1))
        item.attempts = 1
        item.status = status
        await session.commit()

        with pytest.raises(ConflictError, match="створіть нову гру"):
            await DrawService().cancel_draw(session, settings, settings.admin_telegram_id, game_id)

        assert (await session.get(Game, game_id)).status == "DRAWN"
        assert await session.scalar(select(func.count()).select_from(Assignment)) == 4
        assert await session.scalar(select(func.count()).select_from(NotificationOutbox)) == 4


@pytest.mark.asyncio
async def test_wishlist_is_returned_only_for_requesters_assignment(
    session_factory, settings
) -> None:
    async with session_factory() as session:
        game, participants = await create_game(session, settings)
        game_id = game.id
        service = WishlistService()
        await service.update(session, 20002, game_id, "Книжка https://example.com/book")
        await DrawService().draw(
            session,
            settings,
            settings.admin_telegram_id,
            game_id,
            random.Random(8),
        )
        assignment = await session.scalar(
            select(Assignment).where(
                Assignment.game_id == game_id,
                Assignment.receiver_id == participants[1].id,
            )
        )
        giver = await session.get(Participant, assignment.giver_id)
        user = await session.get(User, giver.user_id)
        recipient_name, wishlist = await service.recipient_wishlist(
            session, user.telegram_id, game_id
        )
        assert recipient_name == participants[1].display_name
        assert wishlist == "Книжка https://example.com/book"

        await session.commit()
        outsider = await UserService().register(session, 29999, "Outsider", None)
        with pytest.raises(NotFoundError):
            await service.recipient_wishlist(session, outsider.telegram_id, game_id)


class RecordingBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, parse_mode: str) -> None:
        self.sent.append((chat_id, text))


@pytest.mark.asyncio
async def test_outbox_sends_from_saved_assignment_and_marks_delivered(
    session_factory, settings
) -> None:
    async with session_factory() as session:
        game, _ = await create_game(session, settings)
        await DrawService().draw(
            session,
            settings,
            settings.admin_telegram_id,
            game.id,
            random.Random(2),
        )
    bot = RecordingBot()
    assert await OutboxService().deliver_one(bot, session_factory)
    assert len(bot.sent) == 1
    assert "Ви даруєте подарунок" in bot.sent[0][1]
    async with session_factory() as session:
        delivered = await session.scalar(
            select(func.count())
            .select_from(NotificationOutbox)
            .where(NotificationOutbox.status == "DELIVERED")
        )
        assert delivered == 1


class FailingBot:
    async def send_message(self, chat_id: int, text: str, parse_mode: str) -> None:
        raise TelegramAPIError(
            method=SendMessage(chat_id=chat_id, text=text),
            message="test delivery failure",
        )


@pytest.mark.asyncio
async def test_failed_outbox_delivery_is_retryable(session_factory, settings) -> None:
    async with session_factory() as session:
        game, _ = await create_game(session, settings)
        game_id = game.id
        await DrawService().draw(
            session,
            settings,
            settings.admin_telegram_id,
            game_id,
            random.Random(5),
        )
        assert await OutboxService().deliver_one(FailingBot(), session_factory)
        item = await session.scalar(
            select(NotificationOutbox)
            .join(Assignment, Assignment.id == NotificationOutbox.assignment_id)
            .where(Assignment.game_id == game_id)
            .order_by(NotificationOutbox.id)
            .limit(1)
        )
        assert item.status == "PENDING"
        assert item.attempts == 1
        assert item.last_error_code == "TelegramAPIError"

        await session.commit()
        assert (
            await OutboxService().retry_pending(
                session, settings, settings.admin_telegram_id, game_id
            )
            == 4
        )
        successful_bot = RecordingBot()
        assert await OutboxService().deliver_one(successful_bot, session_factory)
        assert len(successful_bot.sent) == 1


@pytest.mark.asyncio
async def test_new_game_requires_closing_current_setup_game(session_factory, settings) -> None:
    async with session_factory() as session:
        await UserService().register(session, settings.admin_telegram_id, "Organizer", None)
        current = await GameService().ensure_initial_game(
            session, settings, settings.admin_telegram_id
        )
        current_id = current.id
        with pytest.raises(InvalidStateError):
            await GameService().create_game(
                session,
                settings,
                settings.admin_telegram_id,
                "Next",
            )
        await GameService().cancel_game(
            session,
            settings,
            settings.admin_telegram_id,
            current_id,
        )
        new_game = await GameService().create_game(
            session,
            settings,
            settings.admin_telegram_id,
            "Next",
        )
        assert new_game.name == "Next"
        assert new_game.status == "SETUP"
