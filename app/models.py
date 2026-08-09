from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RecordingStatus(StrEnum):
    UPLOADED = "uploaded"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


def new_public_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class InterviewRecording(Base):
    __tablename__ = "interview_recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=new_public_id,
    )
    title: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200))
    interview_question: Mapped[str] = mapped_column(Text)
    job_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_filename: Mapped[str] = mapped_column(String(255), unique=True)
    video_mime_type: Mapped[str] = mapped_column(String(100))
    duration_seconds: Mapped[float] = mapped_column(Float)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default=RecordingStatus.UPLOADED.value,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


class InterviewChatMessage(Base):
    __tablename__ = "interview_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recording_id: Mapped[int] = mapped_column(
        ForeignKey("interview_recordings.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
