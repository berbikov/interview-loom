from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, model_validator

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


class GeminiSettingsValidation(BaseModel):
    """A validation request may use the saved desktop key when input is empty."""

    api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)


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


class AnalysisCriteria(BaseModel):
    """Scores used by the result UI and the Gemini structured-output contract."""

    structure: int = Field(ge=0, le=100)
    specificity: int = Field(ge=0, le=100)
    relevance: int = Field(ge=0, le=100)
    clarity: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)

    model_config = ConfigDict(extra="forbid")


class AIAnalysis(BaseModel):
    """Validated contract for the structured Gemini interview analysis."""

    overall_score: int = Field(ge=0, le=100)
    criteria: AnalysisCriteria = Field(
        default_factory=lambda: AnalysisCriteria(
            structure=0,
            specificity=0,
            relevance=0,
            clarity=0,
            confidence=0,
        )
    )
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

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_scores(cls, value: object) -> object:
        """Render analyses saved by the 1–10 score contract without data loss."""
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if "criteria" in payload:
            return payload
        legacy_overall = payload.get("overall_score", 0)
        is_legacy_score = isinstance(legacy_overall, int) and legacy_overall <= 10
        score = int(legacy_overall) * 10 if is_legacy_score else legacy_overall
        payload["overall_score"] = score
        payload["criteria"] = {
            "structure": int(payload.pop("structure_score", 0)) * 10,
            "specificity": int(payload.pop("specificity_score", 0)) * 10,
            "relevance": 50,
            "clarity": int(payload.pop("clarity_score", 0)) * 10,
            "confidence": 50,
        }
        return payload


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
