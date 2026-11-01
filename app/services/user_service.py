from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User


class UserService:
    async def register(
        self,
        session: AsyncSession,
        telegram_id: int,
        first_name: str,
        username: str | None,
    ) -> User:
        async with session.begin():
            user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
            if user is None:
                user = User(
                    telegram_id=telegram_id,
                    first_name=first_name[:128],
                    username=username[:64] if username else None,
                )
                session.add(user)
            else:
                user.first_name = first_name[:128]
                user.username = username[:64] if username else None
            await session.flush()
            return user
