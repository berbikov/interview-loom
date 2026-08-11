from pathlib import Path

import pytest
from google.genai import types

from app.config import Settings
from app.schemas import AIAnalysis
from app.services.gemini import (
    AnalysisRequest,
    GeminiAnalysisService,
    GeminiClient,
    GeminiConfigurationError,
    GoogleGeminiClient,
    InterviewChatRequest,
)
from app.services.secret_store import EnvironmentSecretStore

ANALYSIS_REQUEST = AnalysisRequest(
    transcript="Я отвечал за запуск эксперимента и работу команды.",
    role="Product Manager",
    interview_question="Расскажите о сложном проекте.",
    job_description="Развитие B2B-продукта.",
)


class StubGeminiClient:
    def __init__(self) -> None:
        self.requests: list[AnalysisRequest] = []
        self.validation_calls = 0

    def validate_access(self) -> None:
        self.validation_calls += 1

    def generate_analysis(self, request: AnalysisRequest) -> AIAnalysis:
        self.requests.append(request)
        return AIAnalysis(
            overall_score=7,
            structure_score=7,
            clarity_score=8,
            specificity_score=6,
            summary="Содержательный ответ.",
            strengths=["Понятна роль кандидата"],
            weaknesses=["Мало чисел"],
            filler_words=[],
            recommendations=["Добавить измеримый результат"],
            improved_answer="Я организовал эксперимент и повысил ключевую метрику.",
            follow_up_question="Какой результат дал эксперимент?",
        )

    def generate_chat_reply(self, request: InterviewChatRequest) -> str:
        return f"Разбор вопроса: {request.question}"


def build_settings(tmp_path: Path, api_key: str | None) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'unused.db'}",
        upload_dir=tmp_path / "uploads",
        gemini_api_key=api_key,
    )


def test_missing_gemini_api_key_is_handled_without_client_call(tmp_path: Path) -> None:
    factory_calls = 0

    def factory(api_key: str, settings: Settings) -> GeminiClient:
        nonlocal factory_calls
        factory_calls += 1
        return StubGeminiClient()

    service = GeminiAnalysisService(
        settings=(settings := build_settings(tmp_path, None)),
        secret_store=EnvironmentSecretStore(settings),
        client_factory=factory,
    )

    assert service.is_configured is False
    with pytest.raises(GeminiConfigurationError, match="GEMINI_API_KEY"):
        service.analyze(ANALYSIS_REQUEST)
    assert factory_calls == 0


def test_gemini_service_uses_key_and_returns_validated_analysis(tmp_path: Path) -> None:
    client = StubGeminiClient()
    received_api_keys: list[str] = []

    def factory(api_key: str, settings: Settings) -> GeminiClient:
        received_api_keys.append(api_key)
        return client

    service = GeminiAnalysisService(
        settings=(settings := build_settings(tmp_path, "test-secret")),
        secret_store=EnvironmentSecretStore(settings),
        client_factory=factory,
    )

    result = service.analyze(ANALYSIS_REQUEST)

    assert result.overall_score == 7
    assert received_api_keys == ["test-secret"]
    assert client.requests == [ANALYSIS_REQUEST]


def test_gemini_key_is_validated_without_generating_content(tmp_path: Path) -> None:
    client = StubGeminiClient()
    service = GeminiAnalysisService(
        settings=(settings := build_settings(tmp_path, None)),
        secret_store=EnvironmentSecretStore(settings),
        client_factory=lambda api_key, configured_settings: client,
    )

    service.validate_api_key(" user-owned-key ")

    assert client.validation_calls == 1


class StubSDKResponse:
    def __init__(self, parsed: AIAnalysis) -> None:
        self.parsed = parsed
        self.text = parsed.model_dump_json()


class StubSDKModels:
    def __init__(self, response: StubSDKResponse) -> None:
        self.response = response
        self.model_names: list[str] = []

    def generate_content(
        self,
        model: str,
        contents: str,
        config: types.GenerateContentConfig,
    ) -> StubSDKResponse:
        self.model_names.append(model)
        assert "Product Manager" in contents
        assert config.response_mime_type == "application/json"
        return self.response

    def get(self, *, model: str) -> object:
        self.model_names.append(model)
        return object()


class StubSDKClient:
    def __init__(self, response: StubSDKResponse) -> None:
        self.models = StubSDKModels(response)

    def __enter__(self) -> "StubSDKClient":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object,
    ) -> None:
        return None


def test_google_sdk_adapter_uses_structured_response_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = StubGeminiClient().generate_analysis(ANALYSIS_REQUEST)
    sdk_client = StubSDKClient(StubSDKResponse(expected))
    received_keys: list[str] = []

    def create_sdk_client(
        *,
        api_key: str,
        http_options: types.HttpOptions,
    ) -> StubSDKClient:
        received_keys.append(api_key)
        assert http_options.timeout == 60_000
        return sdk_client

    monkeypatch.setattr("app.services.gemini.genai.Client", create_sdk_client)
    client = GoogleGeminiClient("test-secret", build_settings(tmp_path, None))

    result = client.generate_analysis(ANALYSIS_REQUEST)

    assert result == expected
    assert received_keys == ["test-secret"]
    assert sdk_client.models.model_names == ["gemini-2.5-flash"]


def test_google_sdk_validates_key_by_reading_model_without_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = StubGeminiClient().generate_analysis(ANALYSIS_REQUEST)
    sdk_client = StubSDKClient(StubSDKResponse(expected))

    monkeypatch.setattr(
        "app.services.gemini.genai.Client",
        lambda **_: sdk_client,
    )
    client = GoogleGeminiClient("test-secret", build_settings(tmp_path, None))

    client.validate_access()

    assert sdk_client.models.model_names == ["gemini-2.5-flash"]
