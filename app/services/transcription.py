import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Protocol

from faster_whisper import WhisperModel

from app.config import Settings

logger = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    detected_language: str
    duration_seconds: float


class TranscriptionServiceProtocol(Protocol):
    def transcribe(self, media_path: Path) -> TranscriptionResult: ...


class TranscriptionService:
    """Lazily loads one faster-whisper model and serializes CPU inference."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: WhisperModel | None = None
        self._model_lock = Lock()
        self._transcription_lock = Lock()

    def _get_model(self) -> WhisperModel:
        with self._model_lock:
            if self._model is None:
                self.settings.whisper_model_dir.mkdir(parents=True, exist_ok=True)
                logger.info(
                    "Loading faster-whisper model: model=%s device=%s compute_type=%s",
                    self.settings.whisper_model_size,
                    self.settings.whisper_device,
                    self.settings.whisper_compute_type,
                )
                self._model = WhisperModel(
                    self.settings.whisper_model_size,
                    device=self.settings.whisper_device,
                    compute_type=self.settings.whisper_compute_type,
                    download_root=str(self.settings.whisper_model_dir),
                )
        return self._model

    def transcribe(self, media_path: Path) -> TranscriptionResult:
        if not media_path.is_file():
            raise TranscriptionError("Видеофайл записи не найден.")

        try:
            model = self._get_model()
            with self._transcription_lock:
                segments, info = model.transcribe(
                    str(media_path),
                    language=self.settings.resolved_whisper_language,
                    beam_size=self.settings.whisper_beam_size,
                    vad_filter=True,
                    condition_on_previous_text=False,
                )
                text_parts = [
                    segment.text.strip()
                    for segment in segments
                    if segment.text.strip()
                ]
        except TranscriptionError:
            raise
        except Exception as error:
            logger.exception("faster-whisper transcription failed for %s", media_path.name)
            raise TranscriptionError(
                "Не удалось расшифровать запись. Проверьте видео и повторите попытку."
            ) from error

        transcript = " ".join(text_parts).strip()
        if not transcript:
            raise TranscriptionError("В записи не удалось распознать речь.")

        return TranscriptionResult(
            text=transcript,
            detected_language=info.language,
            duration_seconds=float(info.duration),
        )
