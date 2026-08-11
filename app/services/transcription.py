import logging
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Protocol, cast

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
from faster_whisper.transcribe import TranscriptionInfo
from numpy.typing import NDArray

from app.config import Settings

logger = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    detected_language: str
    duration_seconds: float
    raw_text: str | None = None

    @property
    def clean_text(self) -> str:
        return self.text


class TranscriptionServiceProtocol(Protocol):
    def transcribe(
        self,
        media_path: Path,
        language: str | None = None,
    ) -> TranscriptionResult: ...


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

    def transcribe(
        self,
        media_path: Path,
        language: str | None = None,
    ) -> TranscriptionResult:
        if not media_path.is_file():
            raise TranscriptionError("Видеофайл записи не найден.")

        try:
            model = self._get_model()
            with self._transcription_lock:
                selected_language = self.settings.resolve_transcription_language(language)
                audio = self._prepare_audio(media_path)
                text_parts, info = self._transcribe_once(
                    model=model,
                    audio=audio,
                    language=selected_language,
                    vad_filter=self.settings.whisper_vad_filter,
                )
                if not text_parts and self.settings.whisper_vad_filter:
                    logger.info(
                        "No speech after VAD; retrying without VAD: file=%s",
                        media_path.name,
                    )
                    text_parts, info = self._transcribe_once(
                        model=model,
                        audio=audio,
                        language=selected_language,
                        vad_filter=False,
                    )
        except TranscriptionError:
            raise
        except Exception as error:
            logger.exception("faster-whisper transcription failed for %s", media_path.name)
            raise TranscriptionError(
                "Не удалось расшифровать запись. Проверьте видео и повторите попытку."
            ) from error

        raw_transcript = " ".join(text_parts).strip()
        if not raw_transcript:
            raise TranscriptionError("В записи не удалось распознать речь.")
        clean_transcript = self._safe_cleanup(raw_transcript)

        return TranscriptionResult(
            text=clean_transcript,
            detected_language=info.language,
            duration_seconds=float(info.duration),
            raw_text=raw_transcript,
        )

    def _prepare_audio(self, media_path: Path) -> NDArray[np.float32]:
        """Decode losslessly in memory to Whisper's expected mono 16 kHz float audio."""
        audio = cast(
            NDArray[np.float32],
            decode_audio(str(media_path), sampling_rate=16_000, split_stereo=False),
        )
        if audio.size == 0:
            raise TranscriptionError("В видеозаписи не найдена аудиодорожка.")
        if not self.settings.whisper_normalize_audio:
            return audio

        peak = float(abs(audio).max())
        if 0 < peak < 0.1:
            audio = audio * min(0.1 / peak, 8.0)
        return audio

    def _transcribe_once(
        self,
        model: WhisperModel,
        audio: NDArray[np.float32],
        language: str | None,
        vad_filter: bool,
    ) -> tuple[list[str], TranscriptionInfo]:
        segments, info = model.transcribe(
            audio,
            language=language,
            task="transcribe",
            beam_size=self.settings.whisper_beam_size,
            best_of=5,
            temperature=0.0,
            vad_filter=vad_filter,
            vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 300},
            condition_on_previous_text=True,
            no_speech_threshold=0.6,
            hallucination_silence_threshold=1.5,
            chunk_length=30,
            initial_prompt=(
                "Интервью на русском языке. Английские профессиональные термины "
                "могут встречаться без перевода: Product Manager, API, SQL, KPI, "
                "backend, frontend, roadmap, sprint, metrics."
                if language == "ru"
                else None
            ),
        )
        text_parts = [segment.text.strip() for segment in segments if segment.text.strip()]
        return text_parts, info

    @staticmethod
    def _safe_cleanup(raw_transcript: str) -> str:
        """Only normalize whitespace; never remove fillers, repetitions, or meaning."""
        return re.sub(r"\s+", " ", raw_transcript).strip()
