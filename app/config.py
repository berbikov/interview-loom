import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SOURCE_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = Path(
    os.environ.get("INTERVIEW_LOOM_ASSETS_ROOT", str(SOURCE_ROOT))
).resolve()
DESKTOP_MODE = os.environ.get("INTERVIEW_LOOM_DESKTOP", "0") == "1"
CONFIGURED_DATA_ROOT = os.environ.get("INTERVIEW_LOOM_DATA_DIR")
DEFAULT_DATA_ROOT = (
    Path(CONFIGURED_DATA_ROOT).expanduser().resolve()
    if CONFIGURED_DATA_ROOT
    else PROJECT_ROOT / "data"
)
DEFAULT_ENV_FILE = DEFAULT_DATA_ROOT / ".env" if DESKTOP_MODE else PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and an optional .env file."""

    app_name: str = "Interview Loom"
    environment: str = "development"
    database_url: str = f"sqlite:///{DEFAULT_DATA_ROOT / 'app.db'}"
    upload_dir: Path = DEFAULT_DATA_ROOT / "uploads"
    max_upload_size_bytes: int = Field(default=500 * 1024 * 1024, gt=0)
    max_video_duration_seconds: int = Field(default=3_600, gt=0, le=3_600)
    allowed_video_types: tuple[str, ...] = (
        "video/webm",
        "video/mp4",
        "video/quicktime",
        "audio/webm",
    )
    whisper_model_size: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_language: str = "ru"
    whisper_beam_size: int = Field(default=5, ge=1, le=10)
    whisper_vad_filter: bool = True
    whisper_normalize_audio: bool = True
    whisper_model_dir: Path = DEFAULT_DATA_ROOT / "models"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.6-flash"
    gemini_timeout_seconds: int = Field(default=60, ge=5, le=300)
    gemini_retry_attempts: int = Field(default=3, ge=1, le=5)
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_whisper_language(self) -> str | None:
        language = self.whisper_language.strip().lower()
        return None if language in {"", "auto"} else language

    def resolve_transcription_language(self, language: str | None) -> str | None:
        selected_language = (language or self.whisper_language).strip().lower()
        if selected_language not in {"ru", "en", "auto"}:
            selected_language = self.whisper_language.strip().lower()
        return None if selected_language in {"", "auto"} else selected_language

    @property
    def resolved_gemini_api_key(self) -> str | None:
        if self.gemini_api_key is None:
            return None
        api_key = self.gemini_api_key.get_secret_value().strip()
        return api_key or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
