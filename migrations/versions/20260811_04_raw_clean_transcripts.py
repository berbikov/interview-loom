"""Preserve raw STT output separately from the safe display transcript.

Revision ID: 20260811_04
Revises: 20260811_03
Create Date: 2026-08-11
"""

import sqlalchemy as sa
from alembic import op

revision = "20260811_04"
down_revision = "20260811_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("interview_recordings") as batch_op:
        batch_op.add_column(sa.Column("raw_transcript", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("clean_transcript", sa.Text(), nullable=True))
    op.execute(
        "UPDATE interview_recordings "
        "SET raw_transcript = transcript, clean_transcript = transcript "
        "WHERE transcript IS NOT NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("interview_recordings") as batch_op:
        batch_op.drop_column("clean_transcript")
        batch_op.drop_column("raw_transcript")
