import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.database import Database
from app.models import InterviewRecording, RecordingStatus
from app.services.gemini import (
    AnalysisRequest,
    AnalysisServiceProtocol,
    GeminiAnalysisError,
    GeminiConfigurationError,
)
from app.services.transcription import (
    TranscriptionError,
    TranscriptionServiceProtocol,
)

logger = logging.getLogger(__name__)


class RecordingProcessor:
    """Runs transcription and optional AI analysis while persisting each transition."""

    def __init__(
        self,
        database: Database,
        settings: Settings,
        transcription_service: TranscriptionServiceProtocol,
        analysis_service: AnalysisServiceProtocol,
    ) -> None:
        self.database = database
        self.settings = settings
        self.transcription_service = transcription_service
        self.analysis_service = analysis_service

    def process(self, public_id: str) -> None:
        recording_data = self._mark_transcribing(public_id)
        if recording_data is None:
            return
        video_filename, transcription_language = recording_data

        media_path = self.settings.upload_dir / Path(video_filename).name
        try:
            transcription = self.transcription_service.transcribe(
                media_path,
                language=transcription_language,
            )
        except TranscriptionError as error:
            self._mark_failed(public_id, str(error))
            return
        except Exception:
            logger.exception("Unexpected transcription error: public_id=%s", public_id)
            self._mark_failed(public_id, "Не удалось обработать запись из-за внутренней ошибки.")
            return

        analysis_request = self._save_transcript(
            public_id=public_id,
            raw_transcript=transcription.raw_text or transcription.text,
            clean_transcript=transcription.clean_text,
            duration_seconds=transcription.duration_seconds,
        )
        if analysis_request is None:
            return

        self._run_analysis(public_id, analysis_request, transcription.detected_language)

    def analyze_saved_transcript(self, public_id: str) -> None:
        analysis_request = self._mark_analyzing_from_saved_transcript(public_id)
        if analysis_request is None:
            return
        self._run_analysis(public_id, analysis_request)

    def _run_analysis(
        self,
        public_id: str,
        analysis_request: AnalysisRequest,
        detected_language: str | None = None,
    ) -> None:
        try:
            self._mark_ai_analysis_processing(public_id)
            analysis = self.analysis_service.analyze(analysis_request)
        except GeminiConfigurationError as error:
            self._mark_transcription_completed(public_id, str(error))
            logger.info(
                "AI analysis skipped because Gemini is not configured: public_id=%s language=%s",
                public_id,
                detected_language or "saved",
            )
            return
        except GeminiAnalysisError as error:
            self._mark_ai_analysis_failed(public_id, str(error))
            return
        except Exception:
            logger.exception("Unexpected AI analysis error: public_id=%s", public_id)
            self._mark_ai_analysis_failed(
                public_id,
                "Расшифровка готова, но AI-анализ выполнить не удалось.",
            )
            return

        self._save_analysis(public_id, analysis.model_dump_json())

    def recover_interrupted(self) -> int:
        interrupted_statuses = {
            RecordingStatus.UPLOADED.value,
            RecordingStatus.TRANSCRIBING.value,
            RecordingStatus.AI_ANALYSIS_PROCESSING.value,
            "analyzing",
            "processing",
        }
        try:
            with self.database.session() as session:
                recordings = session.scalars(
                    select(InterviewRecording).where(
                        InterviewRecording.status.in_(interrupted_statuses)
                    )
                ).all()
                for recording in recordings:
                    recording.status = RecordingStatus.FAILED.value
                    recording.error_message = (
                        "Обработка была прервана перезапуском приложения. "
                        "Запустите анализ повторно."
                    )
                session.commit()
                return len(recordings)
        except SQLAlchemyError:
            logger.exception("Could not recover interrupted recordings")
            return 0

    def _mark_transcribing(self, public_id: str) -> tuple[str, str] | None:
        try:
            with self.database.session() as session:
                recording = session.scalar(
                    select(InterviewRecording).where(InterviewRecording.public_id == public_id)
                )
                if recording is None:
                    logger.warning("Recording not found for processing: public_id=%s", public_id)
                    return None
                recording.status = RecordingStatus.TRANSCRIBING.value
                recording.analysis_json = None
                recording.error_message = None
                session.commit()
                return recording.video_filename, recording.transcription_language
        except SQLAlchemyError:
            logger.exception("Could not start transcription: public_id=%s", public_id)
            return None

    def _save_transcript(
        self,
        public_id: str,
        raw_transcript: str,
        clean_transcript: str,
        duration_seconds: float,
    ) -> AnalysisRequest | None:
        try:
            with self.database.session() as session:
                recording = session.scalar(
                    select(InterviewRecording).where(InterviewRecording.public_id == public_id)
                )
                if recording is None:
                    return None
                recording.raw_transcript = raw_transcript
                recording.clean_transcript = clean_transcript
                recording.transcript = clean_transcript
                if duration_seconds > 0:
                    recording.duration_seconds = duration_seconds
                recording.status = RecordingStatus.TRANSCRIPTION_COMPLETED.value
                recording.error_message = None
                request = AnalysisRequest(
                    transcript=clean_transcript,
                    role=recording.role,
                    interview_question=recording.interview_question,
                    job_description=recording.job_description,
                )
                session.commit()
                return request
        except SQLAlchemyError:
            logger.exception("Could not save transcript: public_id=%s", public_id)
            self._mark_failed(public_id, "Расшифровка создана, но её не удалось сохранить.")
            return None

    def _mark_analyzing_from_saved_transcript(
        self,
        public_id: str,
    ) -> AnalysisRequest | None:
        try:
            with self.database.session() as session:
                recording = session.scalar(
                    select(InterviewRecording).where(InterviewRecording.public_id == public_id)
                )
                if recording is None or not recording.transcript:
                    return None
                recording.analysis_json = None
                recording.error_message = None
                request = AnalysisRequest(
                    transcript=recording.transcript,
                    role=recording.role,
                    interview_question=recording.interview_question,
                    job_description=recording.job_description,
                )
                session.commit()
                return request
        except SQLAlchemyError:
            logger.exception("Could not start saved transcript analysis: public_id=%s", public_id)
            self._mark_ai_analysis_failed(
                public_id,
                "Не удалось повторно запустить AI-анализ.",
            )
            return None

    def _mark_ai_analysis_processing(self, public_id: str) -> None:
        try:
            with self.database.session() as session:
                recording = session.scalar(
                    select(InterviewRecording).where(InterviewRecording.public_id == public_id)
                )
                if recording is None:
                    return
                recording.status = RecordingStatus.AI_ANALYSIS_PROCESSING.value
                recording.error_message = None
                session.commit()
        except SQLAlchemyError:
            logger.exception("Could not mark AI analysis as processing: public_id=%s", public_id)

    def _save_analysis(self, public_id: str, analysis_json: str) -> None:
        try:
            with self.database.session() as session:
                recording = session.scalar(
                    select(InterviewRecording).where(InterviewRecording.public_id == public_id)
                )
                if recording is None:
                    return
                recording.analysis_json = analysis_json
                recording.status = RecordingStatus.COMPLETED.value
                recording.error_message = None
                session.commit()
        except SQLAlchemyError:
            logger.exception("Could not save AI analysis: public_id=%s", public_id)
            self._mark_ai_analysis_failed(
                public_id,
                "Расшифровка готова, но AI-анализ не удалось сохранить.",
            )
            return
        logger.info("Recording AI analysis completed: public_id=%s", public_id)

    def _mark_transcription_completed(
        self,
        public_id: str,
        message: str,
    ) -> None:
        try:
            with self.database.session() as session:
                recording = session.scalar(
                    select(InterviewRecording).where(InterviewRecording.public_id == public_id)
                )
                if recording is None:
                    return
                recording.status = RecordingStatus.TRANSCRIPTION_COMPLETED.value
                recording.error_message = message
                session.commit()
        except SQLAlchemyError:
            logger.exception("Could not persist transcription-only state: public_id=%s", public_id)

    def _mark_ai_analysis_failed(self, public_id: str, message: str) -> None:
        try:
            with self.database.session() as session:
                recording = session.scalar(
                    select(InterviewRecording).where(InterviewRecording.public_id == public_id)
                )
                if recording is None:
                    return
                recording.status = RecordingStatus.AI_ANALYSIS_FAILED.value
                recording.error_message = message
                session.commit()
        except SQLAlchemyError:
            logger.exception("Could not persist AI analysis failure: public_id=%s", public_id)

    def _mark_failed(self, public_id: str, message: str) -> None:
        try:
            with self.database.session() as session:
                recording = session.scalar(
                    select(InterviewRecording).where(InterviewRecording.public_id == public_id)
                )
                if recording is None:
                    return
                recording.status = RecordingStatus.FAILED.value
                recording.error_message = message
                session.commit()
        except SQLAlchemyError:
            logger.exception("Could not persist failed status: public_id=%s", public_id)
