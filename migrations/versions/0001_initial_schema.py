"""Create initial application schema.

Revision ID: 0001_initial
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64)),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("organizer_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="SETUP", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("drawn_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('SETUP', 'DRAWN', 'CANCELLED')",
            name="ck_games_status",
        ),
        sa.ForeignKeyConstraint(["organizer_id"], ["users.id"], ondelete="RESTRICT"),
    )

    op.create_table(
        "participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("wishlist", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("game_id", "user_id", name="uq_participants_game_user"),
        sa.UniqueConstraint("game_id", "id", name="uq_participants_game_id"),
    )

    op.create_table(
        "exclusions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("participant_a_id", sa.Integer(), nullable=False),
        sa.Column("participant_b_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "participant_a_id < participant_b_id",
            name="ck_exclusions_canonical",
        ),
        sa.ForeignKeyConstraint(
            ["game_id", "participant_a_id"],
            ["participants.game_id", "participants.id"],
            ondelete="CASCADE",
            name="fk_exclusions_first_participant",
        ),
        sa.ForeignKeyConstraint(
            ["game_id", "participant_b_id"],
            ["participants.game_id", "participants.id"],
            ondelete="CASCADE",
            name="fk_exclusions_second_participant",
        ),
        sa.UniqueConstraint(
            "game_id",
            "participant_a_id",
            "participant_b_id",
            name="uq_exclusions_pair",
        ),
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("giver_id", sa.Integer(), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("giver_id <> receiver_id", name="ck_assignments_not_self"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["game_id", "giver_id"],
            ["participants.game_id", "participants.id"],
            ondelete="CASCADE",
            name="fk_assignments_giver",
        ),
        sa.ForeignKeyConstraint(
            ["game_id", "receiver_id"],
            ["participants.game_id", "participants.id"],
            ondelete="CASCADE",
            name="fk_assignments_receiver",
        ),
        sa.UniqueConstraint("game_id", "giver_id", name="uq_assignments_game_giver"),
        sa.UniqueConstraint("game_id", "receiver_id", name="uq_assignments_game_receiver"),
    )

    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(length=80)),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SENDING', 'DELIVERED')",
            name="ck_notification_outbox_status",
        ),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("assignment_id"),
    )


def downgrade() -> None:
    op.drop_table("notification_outbox")
    op.drop_table("assignments")
    op.drop_table("exclusions")
    op.drop_table("participants")
    op.drop_table("games")
    op.drop_table("users")
