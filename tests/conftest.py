from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import AIAnalysis
from app.services.gemini import (
    AnalysisRequest,
    GeminiConfigurationError,
    InterviewChatRequest,
)
from app.services.secret_store import SecretStoreProtocol
from app.services.transcription import TranscriptionResult


class StubTranscriptionService:
    def __init__(self) -> None:
        self.processed_paths: list[Path] = []

    def transcribe(self, media_path: Path) -> TranscriptionResult:
        self.processed_paths.append(media_path)
        return TranscriptionResult(
            text="Это тестовая расшифровка интервью.",
            detected_language="ru",
            duration_seconds=12.5,
        )


class StubAnalysisService:
    is_configured = True

    def __init__(self) -> None:
        self.requests: list[AnalysisRequest] = []

    def analyze(self, request: AnalysisRequest) -> AIAnalysis:
        self.requests.append(request)
        return AIAnalysis(
            overall_score=8,
            structure_score=7,
            clarity_score=8,
            specificity_score=6,
            summary="Ответ понятный, но ему не хватает измеримого результата.",
            strengths=["Чётко описана личная роль", "Ответ соответствует вопросу"],
            weaknesses=["Не назван итоговый результат"],
            filler_words=[],
            recommendations=["Добавьте результат в цифрах", "Используйте структуру STAR"],
            improved_answer=(
                "Я сформулировал гипотезу, организовал эксперимент и измерил результат."
            ),
            follow_up_question="Какой метрикой вы оценивали результат?",
        )

    def chat(self, request: InterviewChatRequest) -> str:
        return f"Оценка опирается на расшифровку. Ваш вопрос: {request.question}"

    def validate_api_key(self, api_key: str) -> None:
        if api_key == "invalid-test-key":
            raise GeminiConfigurationError("Gemini не принял API-ключ.")


class StubSecretStore:
    storage_name = "test_keyring"
    is_editable = True

    def __init__(self) -> None:
        self.api_key: str | None = None

    def get_gemini_api_key(self) -> str | None:
        return self.api_key

    def set_gemini_api_key(self, api_key: str) -> None:
        self.api_key = api_key.strip()

    def delete_gemini_api_key(self) -> None:
        self.api_key = None


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_name="Interview Loom Test",
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        upload_dir=tmp_path / "uploads",
        max_upload_size_bytes=64,
        gemini_api_key=None,
        log_level="CRITICAL",
    )


@pytest.fixture
def transcription_service() -> StubTranscriptionService:
    return StubTranscriptionService()


@pytest.fixture
def analysis_service() -> StubAnalysisService:
    return StubAnalysisService()


@pytest.fixture
def secret_store() -> StubSecretStore:
    return StubSecretStore()


@pytest.fixture
def client(
    test_settings: Settings,
    transcription_service: StubTranscriptionService,
    analysis_service: StubAnalysisService,
    secret_store: SecretStoreProtocol,
) -> Iterator[TestClient]:
    with TestClient(
        create_app(
            test_settings,
            transcription_service=transcription_service,
            analysis_service=analysis_service,
            secret_store=secret_store,
        )
    ) as test_client:
        yield test_client
