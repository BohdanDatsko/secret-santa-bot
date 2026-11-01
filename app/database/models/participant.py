from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.game import Game
    from app.database.models.user import User


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint("game_id", "user_id", name="uq_participants_game_user"),
        UniqueConstraint("game_id", "id", name="uq_participants_game_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    display_name: Mapped[str] = mapped_column(String(160))
    wishlist: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    game: Mapped["Game"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship(back_populates="participants")
