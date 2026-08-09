from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.config import Settings
from app.services.transcription import TranscriptionError, TranscriptionService


@dataclass(frozen=True)
class FakeSegment:
    text: str


@dataclass(frozen=True)
class FakeTranscriptionInfo:
    language: str
    duration: float


def test_transcription_service_reuses_loaded_model(
    tmp_path: Path,
) -> None:
    media_path = tmp_path / "recording.webm"
    media_path.write_bytes(b"test-media")
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'unused.db'}",
        upload_dir=tmp_path / "uploads",
        whisper_model_dir=tmp_path / "models",
    )
    model = Mock()
    model.transcribe.side_effect = [
        (
            iter([FakeSegment(" Первый фрагмент. "), FakeSegment(" Второй. ")]),
            FakeTranscriptionInfo(language="ru", duration=8.0),
        ),
        (
            iter([FakeSegment(" Повторная расшифровка. ")]),
            FakeTranscriptionInfo(language="ru", duration=8.0),
        ),
    ]

    with patch("app.services.transcription.WhisperModel", return_value=model) as constructor:
        service = TranscriptionService(settings)
        first_result = service.transcribe(media_path)
        second_result = service.transcribe(media_path)

    assert first_result.text == "Первый фрагмент. Второй."
    assert second_result.text == "Повторная расшифровка."
    constructor.assert_called_once()


def test_transcription_service_rejects_empty_speech(tmp_path: Path) -> None:
    media_path = tmp_path / "silent.webm"
    media_path.write_bytes(b"test-media")
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'unused.db'}",
        upload_dir=tmp_path / "uploads",
        whisper_model_dir=tmp_path / "models",
    )
    model = Mock()
    model.transcribe.return_value = (
        iter([FakeSegment("   ")]),
        FakeTranscriptionInfo(language="ru", duration=3.0),
    )

    with patch("app.services.transcription.WhisperModel", return_value=model):
        service = TranscriptionService(settings)
        with pytest.raises(TranscriptionError, match="не удалось распознать речь"):
            service.transcribe(media_path)

