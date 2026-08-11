import logging
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import (
    get_analysis_service,
    get_app_settings,
    get_recording_processor,
    get_secret_store,
    get_session,
)
from app.models import ChatRole, InterviewChatMessage, InterviewRecording, RecordingStatus
from app.schemas import (
    ChatHistoryResponse,
    ChatMessageResponse,
    ChatQuestion,
    GeminiSettingsResponse,
    GeminiSettingsUpdate,
    HealthResponse,
    RecordingResponse,
)
from app.services.gemini import (
    AnalysisServiceProtocol,
    ChatTurn,
    GeminiAnalysisError,
    GeminiConfigurationError,
    InterviewChatRequest,
)
from app.services.processing import RecordingProcessor
from app.services.secret_store import SecretStoreError, SecretStoreProtocol
from app.services.storage import (
    EmptyFileError,
    FileTooLargeError,
    InvalidFileTypeError,
    InvalidMediaContainerError,
    save_video_upload,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def find_recording(session: Session, public_id: UUID) -> InterviewRecording | None:
    statement = select(InterviewRecording).where(
        InterviewRecording.public_id == str(public_id)
    )
    return session.scalar(statement)


@router.get("/health", response_model=HealthResponse, tags=["service"])
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


def build_gemini_settings_response(
    secret_store: SecretStoreProtocol,
) -> GeminiSettingsResponse:
    try:
        configured = secret_store.get_gemini_api_key() is not None
    except SecretStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return GeminiSettingsResponse(
        configured=configured,
        editable=secret_store.is_editable,
        storage=secret_store.storage_name,
    )


@router.get(
    "/api/settings/gemini",
    response_model=GeminiSettingsResponse,
    tags=["settings"],
)
def get_gemini_settings(
    secret_store: Annotated[SecretStoreProtocol, Depends(get_secret_store)],
) -> GeminiSettingsResponse:
    return build_gemini_settings_response(secret_store)


@router.put(
    "/api/settings/gemini",
    response_model=GeminiSettingsResponse,
    tags=["settings"],
)
def update_gemini_settings(
    payload: GeminiSettingsUpdate,
    secret_store: Annotated[SecretStoreProtocol, Depends(get_secret_store)],
    analysis_service: Annotated[AnalysisServiceProtocol, Depends(get_analysis_service)],
) -> GeminiSettingsResponse:
    if not secret_store.is_editable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="В веб-режиме ключ настраивается на сервере.",
        )
    api_key = payload.api_key.get_secret_value()
    try:
        analysis_service.validate_api_key(api_key)
        secret_store.set_gemini_api_key(api_key)
    except GeminiConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except SecretStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return build_gemini_settings_response(secret_store)


@router.post(
    "/api/settings/gemini/validate",
    response_model=GeminiSettingsResponse,
    tags=["settings"],
)
def validate_gemini_settings(
    payload: GeminiSettingsUpdate,
    secret_store: Annotated[SecretStoreProtocol, Depends(get_secret_store)],
    analysis_service: Annotated[AnalysisServiceProtocol, Depends(get_analysis_service)],
) -> GeminiSettingsResponse:
    """Check a supplied key without persisting or returning it."""
    if not secret_store.is_editable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="В веб-режиме ключ настраивается на сервере.",
        )
    try:
        analysis_service.validate_api_key(payload.api_key.get_secret_value())
    except GeminiConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    return build_gemini_settings_response(secret_store)


@router.delete(
    "/api/settings/gemini",
    response_model=GeminiSettingsResponse,
    tags=["settings"],
)
def delete_gemini_settings(
    secret_store: Annotated[SecretStoreProtocol, Depends(get_secret_store)],
) -> GeminiSettingsResponse:
    if not secret_store.is_editable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="В веб-режиме ключ настраивается на сервере.",
        )
    try:
        secret_store.delete_gemini_api_key()
    except SecretStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return build_gemini_settings_response(secret_store)


@router.post(
    "/api/recordings",
    response_model=RecordingResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["recordings"],
)
async def create_recording(
    background_tasks: BackgroundTasks,
    video: Annotated[UploadFile, File(description="Видеозапись интервью")],
    title: Annotated[str, Form(min_length=1, max_length=200)],
    role: Annotated[str, Form(min_length=1, max_length=200)],
    interview_question: Annotated[str, Form(min_length=1, max_length=5000)],
    duration_seconds: Annotated[float, Form(ge=0)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    recording_processor: Annotated[
        RecordingProcessor,
        Depends(get_recording_processor),
    ],
    session: Annotated[Session, Depends(get_session)],
    job_description: Annotated[str | None, Form(max_length=10_000)] = None,
    transcription_language: Annotated[str, Form()] = "ru",
) -> RecordingResponse:
    if not title.strip() or not role.strip() or not interview_question.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Название, должность и вопрос не могут быть пустыми.",
        )

    selected_language = transcription_language.strip().lower()
    if selected_language not in {"ru", "en", "auto"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Выберите русский, английский или автоматическое определение языка.",
        )
    if duration_seconds > settings.max_video_duration_seconds:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Длительность видео превышает максимально допустимые 60 минут.",
        )

    try:
        saved_upload = await save_video_upload(
            upload=video,
            upload_dir=settings.upload_dir,
            allowed_video_types=settings.allowed_video_types,
            max_size_bytes=settings.max_upload_size_bytes,
        )
    except InvalidFileTypeError as error:
        logger.warning("Upload rejected because of content type: %s", video.content_type)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from error
    except FileTooLargeError as error:
        logger.warning("Upload rejected because it exceeded the size limit")
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(error),
        ) from error
    except EmptyFileError as error:
        logger.warning("Empty upload rejected")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except InvalidMediaContainerError as error:
        logger.warning("Upload rejected because its container signature is invalid")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    recording = InterviewRecording(
        title=title.strip(),
        role=role.strip(),
        interview_question=interview_question.strip(),
        job_description=job_description.strip() if job_description else None,
        video_filename=saved_upload.stored_filename,
        video_mime_type=saved_upload.content_type,
        transcription_language=selected_language,
        duration_seconds=duration_seconds,
        status=RecordingStatus.UPLOADED.value,
    )
    try:
        session.add(recording)
        session.commit()
        session.refresh(recording)
    except SQLAlchemyError as error:
        session.rollback()
        saved_upload.path.unlink(missing_ok=True)
        logger.exception("Could not persist uploaded recording")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось сохранить запись. Попробуйте ещё раз.",
        ) from error

    logger.info(
        "Recording created: public_id=%s size=%s",
        recording.public_id,
        saved_upload.size_bytes,
    )
    background_tasks.add_task(recording_processor.process, recording.public_id)
    return RecordingResponse.model_validate(recording)


@router.get(
    "/api/recordings/{public_id}",
    response_model=RecordingResponse,
    tags=["recordings"],
)
def get_recording(
    public_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> RecordingResponse:
    recording = find_recording(session, public_id)
    if recording is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись не найдена.",
        )
    return RecordingResponse.model_validate(recording)


@router.get(
    "/api/recordings/{public_id}/chat",
    response_model=ChatHistoryResponse,
    tags=["recordings"],
)
def get_recording_chat(
    public_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ChatHistoryResponse:
    recording = find_recording(session, public_id)
    if recording is None:
        raise HTTPException(status_code=404, detail="Запись не найдена.")
    messages = session.scalars(
        select(InterviewChatMessage)
        .where(InterviewChatMessage.recording_id == recording.id)
        .order_by(InterviewChatMessage.id)
    ).all()
    return ChatHistoryResponse(
        messages=[ChatMessageResponse.model_validate(message) for message in messages]
    )


@router.post(
    "/api/recordings/{public_id}/chat",
    response_model=ChatMessageResponse,
    tags=["recordings"],
)
def ask_recording_chat(
    public_id: UUID,
    payload: ChatQuestion,
    analysis_service: Annotated[
        AnalysisServiceProtocol,
        Depends(get_analysis_service),
    ],
    session: Annotated[Session, Depends(get_session)],
) -> ChatMessageResponse:
    recording = find_recording(session, public_id)
    if recording is None:
        raise HTTPException(status_code=404, detail="Запись не найдена.")
    if not recording.transcript:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала дождитесь завершения расшифровки.",
        )
    previous_messages = session.scalars(
        select(InterviewChatMessage)
        .where(InterviewChatMessage.recording_id == recording.id)
        .order_by(InterviewChatMessage.id.desc())
        .limit(12)
    ).all()
    history = tuple(
        ChatTurn(role=message.role, content=message.content)
        for message in reversed(previous_messages)
    )
    try:
        reply = analysis_service.chat(
            InterviewChatRequest(
                transcript=recording.transcript,
                analysis_json=recording.analysis_json,
                role=recording.role,
                interview_question=recording.interview_question,
                question=payload.question,
                history=history,
            )
        )
    except GeminiConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except GeminiAnalysisError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    user_message = InterviewChatMessage(
        recording_id=recording.id,
        role=ChatRole.USER.value,
        content=payload.question,
    )
    assistant_message = InterviewChatMessage(
        recording_id=recording.id,
        role=ChatRole.ASSISTANT.value,
        content=reply,
    )
    try:
        session.add_all([user_message, assistant_message])
        session.commit()
        session.refresh(assistant_message)
    except SQLAlchemyError as error:
        session.rollback()
        logger.exception("Could not persist AI chat: public_id=%s", public_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось сохранить ответ AI Chat.",
        ) from error
    return ChatMessageResponse.model_validate(assistant_message)


@router.post(
    "/api/recordings/{public_id}/analyze",
    response_model=RecordingResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["recordings"],
)
def restart_recording_analysis(
    public_id: UUID,
    background_tasks: BackgroundTasks,
    recording_processor: Annotated[
        RecordingProcessor,
        Depends(get_recording_processor),
    ],
    session: Annotated[Session, Depends(get_session)],
) -> RecordingResponse:
    recording = find_recording(session, public_id)
    if recording is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись не найдена.",
        )
    if recording.status in {
        RecordingStatus.TRANSCRIBING.value,
        RecordingStatus.ANALYZING.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Обработка этой записи уже выполняется.",
        )

    has_saved_transcript = bool(recording.transcript)
    recording.status = (
        RecordingStatus.ANALYZING.value
        if has_saved_transcript
        else RecordingStatus.UPLOADED.value
    )
    recording.error_message = None
    try:
        session.commit()
        session.refresh(recording)
    except SQLAlchemyError as error:
        session.rollback()
        logger.exception("Could not schedule recording analysis: public_id=%s", public_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось повторно запустить обработку.",
        ) from error

    if has_saved_transcript:
        background_tasks.add_task(recording_processor.analyze_saved_transcript, recording.public_id)
        logger.info("Saved transcript AI analysis restarted: public_id=%s", public_id)
    else:
        background_tasks.add_task(recording_processor.process, recording.public_id)
        logger.info("Recording processing restarted: public_id=%s", public_id)
    return RecordingResponse.model_validate(recording)


@router.get(
    "/recordings/{public_id}/media",
    response_class=FileResponse,
    include_in_schema=False,
)
def get_recording_media(
    public_id: UUID,
    settings: Annotated[Settings, Depends(get_app_settings)],
    session: Annotated[Session, Depends(get_session)],
) -> FileResponse:
    recording = find_recording(session, public_id)
    if recording is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись не найдена.",
        )

    media_path = settings.upload_dir / Path(recording.video_filename).name
    if not media_path.is_file():
        logger.error("Media file is missing for public_id=%s", public_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видеофайл записи не найден.",
        )

    return FileResponse(
        media_path,
        media_type=recording.video_mime_type,
        filename=recording.video_filename,
        content_disposition_type="inline",
    )
