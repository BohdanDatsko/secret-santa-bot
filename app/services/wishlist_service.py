from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database.models.assignment import Assignment
from app.database.models.game import Game
from app.database.models.participant import Participant
from app.database.models.user import User
from app.services.errors import InvalidStateError, NotFoundError


class WishlistService:
    async def update(
        self,
        session: AsyncSession,
        telegram_id: int,
        game_id: int,
        wishlist: str,
    ) -> None:
        clean_wishlist = wishlist.strip()
        if not clean_wishlist or len(clean_wishlist) > 2000:
            raise InvalidStateError("Wishlist має містити від 1 до 2000 символів.")
        async with session.begin():
            user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
            if user is None:
                raise NotFoundError("Спочатку надішліть /start.")
            game = await session.get(Game, game_id)
            if game is None:
                raise NotFoundError("Гру не знайдено.")
            if game.status == "CANCELLED":
                raise InvalidStateError("Wishlist не можна змінювати у скасованій грі.")
            participant = await session.scalar(
                select(Participant).where(
                    Participant.user_id == user.id,
                    Participant.game_id == game_id,
                    Participant.is_active.is_(True),
                )
            )
            if participant is None:
                raise NotFoundError("Ви не є активним учасником цієї гри.")
            participant.wishlist = clean_wishlist

    async def recipient_wishlist(
        self,
        session: AsyncSession,
        telegram_id: int,
        game_id: int,
    ) -> tuple[str, str | None]:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            raise NotFoundError("Спочатку надішліть /start.")
        game = await session.get(Game, game_id)
        if game is None:
            raise NotFoundError("Гру не знайдено.")
        if game.status != "DRAWN":
            raise InvalidStateError("Wishlist отримувача доступний після жеребкування.")
        giver = aliased(Participant)
        result = await session.execute(
            select(Participant.display_name, Participant.wishlist)
            .join(Assignment, Assignment.receiver_id == Participant.id)
            .join(giver, Assignment.giver_id == giver.id)
            .where(
                Assignment.game_id == game_id,
                giver.game_id == game_id,
                giver.user_id == user.id,
            )
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError("У вас немає призначення у цій грі.")
        return row.display_name, row.wishlist
