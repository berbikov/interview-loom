from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints

from app.models import ChatRole, RecordingStatus

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
AnalysisItem = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


class HealthResponse(BaseModel):
    status: str


class GeminiSettingsResponse(BaseModel):
    configured: bool
    editable: bool
    storage: str


class GeminiSettingsUpdate(BaseModel):
    api_key: SecretStr = Field(min_length=8, max_length=500)


class RecordingResponse(BaseModel):
    public_id: UUID
    title: str
    role: str
    interview_question: str
    job_description: str | None
    video_filename: str
    video_mime_type: str
    transcription_language: str
    duration_seconds: float
    raw_transcript: str | None
    clean_transcript: str | None
    transcript: str | None
    analysis_json: str | None
    status: RecordingStatus
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FillerWord(BaseModel):
    word: AnalysisItem
    count: int = Field(ge=1)

    model_config = ConfigDict(extra="forbid")


class AIAnalysis(BaseModel):
    """Validated contract for the structured Gemini interview analysis."""

    overall_score: int = Field(ge=1, le=10)
    structure_score: int = Field(ge=1, le=10)
    clarity_score: int = Field(ge=1, le=10)
    specificity_score: int = Field(ge=1, le=10)
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    strengths: list[AnalysisItem] = Field(min_length=1, max_length=10)
    weaknesses: list[AnalysisItem] = Field(min_length=1, max_length=10)
    filler_words: list[FillerWord] = Field(max_length=30)
    recommendations: list[AnalysisItem] = Field(min_length=1, max_length=10)
    improved_answer: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000),
    ]
    follow_up_question: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000),
    ]

    model_config = ConfigDict(extra="forbid")


class ChatQuestion(BaseModel):
    question: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000),
    ]


class ChatMessageResponse(BaseModel):
    id: int
    role: ChatRole
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageResponse]
