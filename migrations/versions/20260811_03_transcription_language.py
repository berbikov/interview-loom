"""Store the language selected for each interview recording.

Revision ID: 20260811_03
Revises: 20260809_02
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa

revision = "20260811_03"
down_revision = "20260809_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("interview_recordings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "transcription_language",
                sa.String(length=10),
                nullable=False,
                server_default="ru",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("interview_recordings") as batch_op:
        batch_op.drop_column("transcription_language")
