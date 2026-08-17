"""Separate transcript availability from Gemini analysis completion.

Revision ID: 20260811_05
Revises: 20260811_04
Create Date: 2026-08-11
"""

from alembic import op

revision = "20260811_05"
down_revision = "20260811_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE interview_recordings "
        "SET status = 'transcription_completed' "
        "WHERE status = 'completed' "
        "AND transcript IS NOT NULL "
        "AND (analysis_json IS NULL OR analysis_json = '')"
    )
    op.execute(
        "UPDATE interview_recordings "
        "SET status = 'ai_analysis_processing' "
        "WHERE status = 'analyzing'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE interview_recordings SET status = 'completed' "
        "WHERE status IN ('transcription_completed', 'ai_analysis_failed')"
    )
    op.execute(
        "UPDATE interview_recordings SET status = 'analyzing' "
        "WHERE status = 'ai_analysis_processing'"
    )
