import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.templating import Jinja2Templates

from app.config import PROJECT_ROOT, Settings
from app.dependencies import get_app_settings, get_secret_store, get_session
from app.metadata import APP_VERSION
from app.models import InterviewRecording
from app.routers.api import find_recording
from app.schemas import AIAnalysis
from app.services.secret_store import SecretStoreError, SecretStoreProtocol

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=PROJECT_ROOT / "app" / "templates")
templates.env.globals["app_version"] = APP_VERSION
logger = logging.getLogger(__name__)
MACOS_PACKAGE_PATH = PROJECT_ROOT / "release" / "Interview-Loom-macOS-arm64.zip"
WINDOWS_PACKAGE_PATH = PROJECT_ROOT / "release" / "Interview-Loom-Setup-x64.exe"


@router.get("/", response_class=HTMLResponse)
def index_page(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    recent_recordings = session.scalars(
        select(InterviewRecording)
        .order_by(InterviewRecording.created_at.desc())
        .limit(6)
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"recent_recordings": recent_recordings},
    )


@router.get("/record", response_class=HTMLResponse)
def record_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="record.html",
        context={
            "max_upload_size_bytes": settings.max_upload_size_bytes,
            "max_video_duration_seconds": settings.max_video_duration_seconds,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    secret_store: Annotated[SecretStoreProtocol, Depends(get_secret_store)],
) -> HTMLResponse:
    try:
        gemini_configured = secret_store.get_gemini_api_key() is not None
        settings_error = None
    except SecretStoreError as error:
        gemini_configured = False
        settings_error = str(error)
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "gemini_configured": gemini_configured,
            "settings_editable": secret_store.is_editable,
            "settings_error": settings_error,
        },
    )


@router.get("/download/macos", response_class=FileResponse, response_model=None)
def download_macos_app(request: Request) -> Response:
    if not MACOS_PACKAGE_PATH.is_file():
        return templates.TemplateResponse(
            request=request,
            name="download_unavailable.html",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return FileResponse(
        MACOS_PACKAGE_PATH,
        media_type="application/zip",
        filename=MACOS_PACKAGE_PATH.name,
    )


@router.get("/download/windows", response_class=FileResponse, response_model=None)
def download_windows_app(request: Request) -> Response:
    if not WINDOWS_PACKAGE_PATH.is_file():
        return templates.TemplateResponse(
            request=request,
            name="download_unavailable.html",
            context={"platform_name": "Windows"},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return FileResponse(
        WINDOWS_PACKAGE_PATH,
        media_type="application/vnd.microsoft.portable-executable",
        filename=WINDOWS_PACKAGE_PATH.name,
    )


@router.get("/recordings/{public_id}", response_class=HTMLResponse)
def result_page(
    request: Request,
    public_id: UUID,
    settings: Annotated[Settings, Depends(get_app_settings)],
    secret_store: Annotated[SecretStoreProtocol, Depends(get_secret_store)],
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    recording = find_recording(session, public_id)
    if recording is None:
        return templates.TemplateResponse(
            request=request,
            name="not_found.html",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    analysis: AIAnalysis | None = None
    if recording.analysis_json:
        try:
            analysis = AIAnalysis.model_validate_json(recording.analysis_json)
        except ValidationError:
            logger.warning("Could not render stored analysis: public_id=%s", public_id)

    try:
        gemini_configured = secret_store.get_gemini_api_key() is not None
    except SecretStoreError:
        gemini_configured = False

    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "recording": recording,
            "analysis": analysis,
            "gemini_configured": gemini_configured,
        },
    )
