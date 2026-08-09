"""Add persisted AI chat messages.

Revision ID: 20260809_02
Revises: 20260809_01
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_02"
down_revision: str | None = "20260809_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "interview_chat_messages" in inspector.get_table_names():
        return
    op.create_table(
        "interview_chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recording_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["recording_id"],
            ["interview_recordings.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_interview_chat_messages_recording_id",
        "interview_chat_messages",
        ["recording_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_chat_messages_recording_id",
        table_name="interview_chat_messages",
    )
    op.drop_table("interview_chat_messages")
