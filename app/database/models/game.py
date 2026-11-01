from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.participant import Participant


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SETUP', 'DRAWN', 'CANCELLED')",
            name="ck_games_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default="SETUP", server_default="SETUP")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    drawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    participants: Mapped[list["Participant"]] = relationship(back_populates="game")
