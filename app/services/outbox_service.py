import asyncio
import html
import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from app.config import Settings
from app.database.models.assignment import Assignment
from app.database.models.game import Game
from app.database.models.notification_outbox import NotificationOutbox
from app.database.models.participant import Participant
from app.database.models.user import User
from app.services.common import require_organizer
from app.services.errors import NotFoundError

logger = logging.getLogger(__name__)
LEASE_DURATION = timedelta(minutes=5)


class OutboxService:
    async def retry_pending(
        self,
        session: AsyncSession,
        settings: Settings,
        actor_telegram_id: int,
        game_id: int,
    ) -> int:
        async with session.begin():
            game = await session.get(Game, game_id)
            if game is None:
                raise NotFoundError("Гру не знайдено.")
            await require_organizer(session, settings, game, actor_telegram_id)
            result = await session.execute(
                update(NotificationOutbox)
                .where(
                    NotificationOutbox.assignment_id.in_(
                        select(Assignment.id).where(Assignment.game_id == game_id)
                    ),
                    NotificationOutbox.status == "PENDING",
                )
                .values(next_attempt_at=datetime.now(UTC))
            )
            return result.rowcount or 0

    async def deliver_one(
        self,
        bot: Bot,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> bool:
        now = datetime.now(UTC)
        async with session_factory() as session, session.begin():
            item = await session.scalar(
                select(NotificationOutbox)
                .where(
                    or_(
                        and_(
                            NotificationOutbox.status == "PENDING",
                            NotificationOutbox.next_attempt_at <= now,
                        ),
                        and_(
                            NotificationOutbox.status == "SENDING",
                            NotificationOutbox.lease_until <= now,
                        ),
                    )
                )
                .order_by(NotificationOutbox.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if item is None:
                return False
            item.status = "SENDING"
            item.attempts += 1
            item.lease_until = now + LEASE_DURATION
            payload = await self._payload(session, item.assignment_id)
            outbox_id = item.id
            attempts = item.attempts

        try:
            await bot.send_message(
                chat_id=payload[0],
                text=self._message(payload[1], payload[2]),
                parse_mode="HTML",
            )
        except TelegramAPIError as error:
            retry_at = datetime.now(UTC) + timedelta(
                seconds=min(3600, 30 * (2 ** min(attempts - 1, 7)))
            )
            async with session_factory() as session, session.begin():
                item = await session.get(NotificationOutbox, outbox_id)
                if item is not None:
                    item.status = "PENDING"
                    item.next_attempt_at = retry_at
                    item.lease_until = None
                    item.last_error_code = type(error).__name__[:80]
            logger.warning(
                "Outbox delivery failed; retry scheduled (error=%s)",
                type(error).__name__,
            )
            return True

        async with session_factory() as session, session.begin():
            item = await session.get(NotificationOutbox, outbox_id)
            if item is not None:
                item.status = "DELIVERED"
                item.delivered_at = datetime.now(UTC)
                item.lease_until = None
                item.last_error_code = None
        return True

    async def _payload(
        self,
        session: AsyncSession,
        assignment_id: int,
    ) -> tuple[int, str, str | None]:
        giver = aliased(Participant)
        receiver = aliased(Participant)
        giver_user = aliased(User)
        result = await session.execute(
            select(
                giver_user.telegram_id,
                receiver.display_name,
                receiver.wishlist,
            )
            .select_from(Assignment)
            .join(giver, Assignment.giver_id == giver.id)
            .join(giver_user, giver.user_id == giver_user.id)
            .join(receiver, Assignment.receiver_id == receiver.id)
            .where(Assignment.id == assignment_id)
        )
        row = result.one()
        return row[0], row[1], row[2]

    @staticmethod
    def _message(recipient_name: str, wishlist: str | None) -> str:
        return (
            "🎁 Ваш результат жеребкування «Секретний Миколай»!\n"
            f"Ви даруєте подарунок: <b>{html.escape(recipient_name)}</b>\n\n"
            f"<b>Wishlist:</b>\n{html.escape(wishlist or 'Wishlist не вказано.')}"
        )


async def run_outbox_worker(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = OutboxService()
    while True:
        try:
            delivered_or_attempted = await service.deliver_one(bot, session_factory)
        except SQLAlchemyError as error:
            logger.warning(
                "Outbox database operation failed; retrying (error=%s)",
                type(error).__name__,
            )
            await asyncio.sleep(5)
            continue
        if not delivered_or_attempted:
            await asyncio.sleep(5)
