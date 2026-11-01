from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Exclusion(Base):
    __tablename__ = "exclusions"
    __table_args__ = (
        CheckConstraint("participant_a_id < participant_b_id", name="ck_exclusions_canonical"),
        UniqueConstraint(
            "game_id", "participant_a_id", "participant_b_id", name="uq_exclusions_pair"
        ),
        ForeignKeyConstraint(
            ["game_id", "participant_a_id"],
            ["participants.game_id", "participants.id"],
            ondelete="CASCADE",
            name="fk_exclusions_first_participant",
        ),
        ForeignKeyConstraint(
            ["game_id", "participant_b_id"],
            ["participants.game_id", "participants.id"],
            ondelete="CASCADE",
            name="fk_exclusions_second_participant",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column()
    participant_a_id: Mapped[int] = mapped_column()
    participant_b_id: Mapped[int] = mapped_column()
