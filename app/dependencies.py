from collections.abc import Iterator
from typing import cast

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Database
from app.services.gemini import AnalysisServiceProtocol
from app.services.processing import RecordingProcessor
from app.services.secret_store import SecretStoreProtocol


def get_database(request: Request) -> Database:
    return cast(Database, request.app.state.database)


def get_app_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_recording_processor(request: Request) -> RecordingProcessor:
    return cast(RecordingProcessor, request.app.state.recording_processor)


def get_secret_store(request: Request) -> SecretStoreProtocol:
    return cast(SecretStoreProtocol, request.app.state.secret_store)


def get_analysis_service(request: Request) -> AnalysisServiceProtocol:
    return cast(AnalysisServiceProtocol, request.app.state.analysis_service)


def get_session(request: Request) -> Iterator[Session]:
    database = get_database(request)
    with database.session() as session:
        yield session
