"""Create interview recordings table.

Revision ID: 20260809_01
Revises:
Create Date: 2026-08-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "interview_recordings" in inspector.get_table_names():
        return
    op.create_table(
        "interview_recordings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=200), nullable=False),
        sa.Column("interview_question", sa.Text(), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("video_filename", sa.String(length=255), nullable=False),
        sa.Column("video_mime_type", sa.String(length=100), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("analysis_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_filename"),
    )
    op.create_index(
        "ix_interview_recordings_public_id",
        "interview_recordings",
        ["public_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_interview_recordings_public_id", table_name="interview_recordings")
    op.drop_table("interview_recordings")
