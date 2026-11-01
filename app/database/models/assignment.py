from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("giver_id <> receiver_id", name="ck_assignments_not_self"),
        UniqueConstraint("game_id", "giver_id", name="uq_assignments_game_giver"),
        UniqueConstraint("game_id", "receiver_id", name="uq_assignments_game_receiver"),
        ForeignKeyConstraint(
            ["game_id", "giver_id"],
            ["participants.game_id", "participants.id"],
            ondelete="CASCADE",
            name="fk_assignments_giver",
        ),
        ForeignKeyConstraint(
            ["game_id", "receiver_id"],
            ["participants.game_id", "participants.id"],
            ondelete="CASCADE",
            name="fk_assignments_receiver",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    giver_id: Mapped[int] = mapped_column()
    receiver_id: Mapped[int] = mapped_column()
