import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import DESKTOP_MODE, PROJECT_ROOT, Settings, get_settings
from app.database import Database
from app.metadata import APP_VERSION
from app.migrations import upgrade_database
from app.routers import api, pages
from app.security import security_middleware
from app.services.gemini import AnalysisServiceProtocol, GeminiAnalysisService
from app.services.processing import RecordingProcessor
from app.services.secret_store import SecretStoreProtocol, create_secret_store
from app.services.transcription import (
    TranscriptionService,
    TranscriptionServiceProtocol,
)

logger = logging.getLogger(__name__)


def configure_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger().setLevel(level)


def create_app(
    settings: Settings | None = None,
    transcription_service: TranscriptionServiceProtocol | None = None,
    analysis_service: AnalysisServiceProtocol | None = None,
    secret_store: SecretStoreProtocol | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    database = Database(resolved_settings.database_url)
    resolved_transcription_service = (
        transcription_service or TranscriptionService(resolved_settings)
    )
    resolved_secret_store = secret_store or create_secret_store(
        resolved_settings,
        desktop_mode=DESKTOP_MODE,
    )
    resolved_analysis_service = analysis_service or GeminiAnalysisService(
        resolved_settings,
        resolved_secret_store,
    )
    recording_processor = RecordingProcessor(
        database=database,
        settings=resolved_settings,
        transcription_service=resolved_transcription_service,
        analysis_service=resolved_analysis_service,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        resolved_settings.upload_dir.mkdir(parents=True, exist_ok=True)
        upgrade_database(resolved_settings.database_url, PROJECT_ROOT)
        interrupted_count = recording_processor.recover_interrupted()
        if interrupted_count:
            logger.warning(
                "Marked interrupted recordings as failed: count=%s",
                interrupted_count,
            )
        logger.info("Application started in %s environment", resolved_settings.environment)
        yield
        database.dispose()
        logger.info("Application stopped")

    application = FastAPI(
        title=resolved_settings.app_name,
        version=APP_VERSION,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.database = database
    application.state.recording_processor = recording_processor
    application.state.analysis_service = resolved_analysis_service
    application.state.secret_store = resolved_secret_store
    application.state.desktop_mode = DESKTOP_MODE
    application.middleware("http")(security_middleware)
    application.mount(
        "/static",
        StaticFiles(directory=PROJECT_ROOT / "app" / "static"),
        name="static",
    )
    application.include_router(api.router)
    application.include_router(pages.router)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        logger.warning(
            "Request validation failed: path=%s errors=%s",
            request.url.path,
            len(error.errors()),
        )
        return JSONResponse(
            status_code=422,
            content={"detail": "Данные запроса не прошли проверку."},
        )

    return application


app = create_app()
