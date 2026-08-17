from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import AIAnalysis
from app.services.gemini import (
    AnalysisRequest,
    GeminiAnalysisError,
    InterviewChatRequest,
)
from app.services.transcription import TranscriptionError, TranscriptionResult
from tests.conftest import StubAnalysisService, StubTranscriptionService

RECORDING_FORM = {
    "title": "Тренировка продуктового интервью",
    "role": "Product Manager",
    "interview_question": "Расскажите о сложном проекте.",
    "job_description": "Работа с продуктовой командой и аналитикой.",
    "duration_seconds": "42.5",
}


def create_test_recording(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/recordings",
        data=RECORDING_FORM,
        files={"video": ("interview.webm", b"\x1a\x45\xdf\xa3valid-video", "video/webm")},
    )
    assert response.status_code == 201
    return response.json()


def test_create_recording(client: TestClient) -> None:
    payload = create_test_recording(client)

    assert payload["title"] == RECORDING_FORM["title"]
    assert payload["role"] == RECORDING_FORM["role"]
    assert payload["status"] == "uploaded"
    assert payload["duration_seconds"] == 42.5
    assert payload["transcript"] is None
    assert payload["analysis_json"] is None
    assert payload["transcription_language"] == "ru"
    assert payload["public_id"]


def test_rejects_invalid_file_type(client: TestClient) -> None:
    response = client.post(
        "/api/recordings",
        data=RECORDING_FORM,
        files={"video": ("notes.txt", b"not-a-video", "text/plain")},
    )

    assert response.status_code == 415
    assert "WebM" in response.json()["detail"]


def test_rejects_file_over_maximum_size(client: TestClient) -> None:
    response = client.post(
        "/api/recordings",
        data=RECORDING_FORM,
        files={"video": ("large.webm", b"\x1a\x45\xdf\xa3" + b"x" * 61, "video/webm")},
    )

    assert response.status_code == 413
    assert "Размер видео" in response.json()["detail"]


def test_rejects_video_longer_than_configured_limit(client: TestClient) -> None:
    response = client.post(
        "/api/recordings",
        data={**RECORDING_FORM, "duration_seconds": "3601"},
        files={"video": ("interview.webm", b"\x1a\x45\xdf\xa3valid-video", "video/webm")},
    )

    assert response.status_code == 413
    assert "60 минут" in response.json()["detail"]


def test_rejects_mismatched_media_container(client: TestClient) -> None:
    response = client.post(
        "/api/recordings",
        data=RECORDING_FORM,
        files={"video": ("fake.webm", b"this-is-not-webm", "video/webm")},
    )

    assert response.status_code == 400
    assert "не соответствует" in response.json()["detail"]


def test_get_recording_by_public_id(client: TestClient) -> None:
    created = create_test_recording(client)
    public_id = str(created["public_id"])

    response = client.get(f"/api/recordings/{public_id}")

    assert response.status_code == 200
    assert response.json()["public_id"] == public_id
    assert response.json()["interview_question"] == RECORDING_FORM["interview_question"]
    assert response.json()["status"] == "completed"
    assert response.json()["transcript"] == "Это тестовая расшифровка интервью."
    assert response.json()["raw_transcript"] == "Это тестовая расшифровка интервью."
    assert response.json()["clean_transcript"] == "Это тестовая расшифровка интервью."
    assert '"overall_score":8' in response.json()["analysis_json"]


def test_automatic_transcription_runs_after_upload(
    client: TestClient,
    transcription_service: StubTranscriptionService,
    analysis_service: StubAnalysisService,
) -> None:
    created = create_test_recording(client)

    response = client.get(f"/api/recordings/{created['public_id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["duration_seconds"] == 12.5
    assert len(transcription_service.processed_paths) == 1
    assert len(analysis_service.requests) == 1
    assert analysis_service.requests[0].role == RECORDING_FORM["role"]


def test_recording_saves_selected_transcription_language(client: TestClient) -> None:
    response = client.post(
        "/api/recordings",
        data={**RECORDING_FORM, "transcription_language": "en"},
        files={"video": ("interview.webm", b"\x1a\x45\xdf\xa3valid-video", "video/webm")},
    )

    assert response.status_code == 201
    assert response.json()["transcription_language"] == "en"


def test_restart_recording_analysis(
    client: TestClient,
    transcription_service: StubTranscriptionService,
    analysis_service: StubAnalysisService,
) -> None:
    created = create_test_recording(client)
    public_id = str(created["public_id"])

    response = client.post(f"/api/recordings/{public_id}/analyze")
    refreshed = client.get(f"/api/recordings/{public_id}")

    assert response.status_code == 202
    assert response.json()["status"] == "transcription_completed"
    assert refreshed.json()["status"] == "completed"
    assert len(transcription_service.processed_paths) == 1
    assert len(analysis_service.requests) == 2


class FailingTranscriptionService:
    def transcribe(
        self,
        media_path: Path,
        language: str | None = None,
    ) -> TranscriptionResult:
        raise TranscriptionError("Тестовая ошибка транскрибации.")


def test_transcription_error_is_saved(
    test_settings: Settings,
) -> None:
    application = create_app(
        test_settings,
        transcription_service=FailingTranscriptionService(),
        analysis_service=StubAnalysisService(),
    )
    with TestClient(application) as failing_client:
        created = create_test_recording(failing_client)
        response = failing_client.get(
            f"/api/recordings/{created['public_id']}"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_message"] == "Тестовая ошибка транскрибации."


class FailingAnalysisService:
    is_configured = True

    def analyze(self, request: AnalysisRequest) -> AIAnalysis:
        raise GeminiAnalysisError("Gemini временно недоступен.")

    def chat(self, request: InterviewChatRequest) -> str:
        raise GeminiAnalysisError("Gemini временно недоступен.")


class AnalysisFailingChatWorkingService(FailingAnalysisService):
    def chat(self, request: InterviewChatRequest) -> str:
        return f"Ответ по расшифровке: {request.question}"


def test_gemini_error_preserves_transcript(test_settings: Settings) -> None:
    application = create_app(
        test_settings,
        transcription_service=StubTranscriptionService(),
        analysis_service=FailingAnalysisService(),
    )
    with TestClient(application) as failing_client:
        created = create_test_recording(failing_client)
        response = failing_client.get(f"/api/recordings/{created['public_id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "ai_analysis_failed"
    assert response.json()["transcript"] == "Это тестовая расшифровка интервью."
    assert response.json()["analysis_json"] is None
    assert response.json()["error_message"] == "Gemini временно недоступен."


def test_missing_key_completes_with_transcript_only(test_settings: Settings) -> None:
    application = create_app(
        test_settings,
        transcription_service=StubTranscriptionService(),
    )
    with TestClient(application) as no_key_client:
        created = create_test_recording(no_key_client)
        response = no_key_client.get(f"/api/recordings/{created['public_id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "transcription_completed"
    assert response.json()["transcript"] == "Это тестовая расшифровка интервью."
    assert response.json()["analysis_json"] is None
    assert "Добавьте Gemini API key" in response.json()["error_message"]


def test_ai_chat_uses_saved_transcript_when_automatic_analysis_failed(
    test_settings: Settings,
) -> None:
    application = create_app(
        test_settings,
        transcription_service=StubTranscriptionService(),
        analysis_service=AnalysisFailingChatWorkingService(),
    )
    with TestClient(application) as failing_client:
        created = create_test_recording(failing_client)
        response = failing_client.post(
            f"/api/recordings/{created['public_id']}/chat",
            json={"question": "Что улучшить?"},
        )

    assert response.status_code == 200
    assert "Что улучшить?" in response.json()["content"]


def test_result_page_contains_polling_client(client: TestClient) -> None:
    created = create_test_recording(client)

    response = client.get(f"/recordings/{created['public_id']}")

    assert response.status_code == 200
    assert "/static/js/result.js" in response.text
    assert "Расшифровка ответа" in response.text
    assert "AI-разбор" in response.text
    assert "AI Chat" in response.text


def test_ai_chat_uses_recording_context_and_persists_history(
    client: TestClient,
) -> None:
    created = create_test_recording(client)
    public_id = str(created["public_id"])

    response = client.post(
        f"/api/recordings/{public_id}/chat",
        json={"question": "Почему снижена конкретика?"},
    )
    history = client.get(f"/api/recordings/{public_id}/chat")

    assert response.status_code == 200
    assert response.json()["role"] == "assistant"
    assert "Почему снижена конкретика?" in response.json()["content"]
    assert history.status_code == 200
    assert [message["role"] for message in history.json()["messages"]] == [
        "user",
        "assistant",
    ]


def test_training_flow_automatically_analyzes_and_continues_in_chat(
    client: TestClient,
    transcription_service: StubTranscriptionService,
    analysis_service: StubAnalysisService,
) -> None:
    """The critical happy path must not require a second Whisper or Gemini request."""
    created = create_test_recording(client)
    public_id = str(created["public_id"])

    result = client.get(f"/api/recordings/{public_id}")
    chat = client.post(
        f"/api/recordings/{public_id}/chat",
        json={"question": "Как мне сделать ответ конкретнее?"},
    )

    assert result.status_code == 200
    assert result.json()["status"] == "completed"
    assert result.json()["transcript"] == "Это тестовая расшифровка интервью."
    assert result.json()["analysis_json"] is not None
    assert len(transcription_service.processed_paths) == 1
    assert len(analysis_service.requests) == 1
    assert chat.status_code == 200
    assert "Как мне сделать ответ конкретнее?" in chat.json()["content"]


def test_ai_chat_rejects_empty_question(client: TestClient) -> None:
    created = create_test_recording(client)
    response = client.post(
        f"/api/recordings/{created['public_id']}/chat",
        json={"question": "   "},
    )

    assert response.status_code == 422
