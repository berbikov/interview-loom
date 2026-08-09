from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


class UploadValidationError(ValueError):
    pass


class InvalidFileTypeError(UploadValidationError):
    pass


class FileTooLargeError(UploadValidationError):
    pass


class EmptyFileError(UploadValidationError):
    pass


class InvalidMediaContainerError(UploadValidationError):
    pass


@dataclass(frozen=True, slots=True)
class SavedUpload:
    original_filename: str
    stored_filename: str
    content_type: str
    size_bytes: int
    path: Path


CONTENT_TYPE_EXTENSIONS: dict[str, str] = {
    "video/webm": ".webm",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "audio/webm": ".webm",
}


def normalize_content_type(content_type: str | None) -> str:
    if content_type is None:
        return ""
    return content_type.split(";", maxsplit=1)[0].strip().lower()


def has_expected_container_signature(content_type: str, prefix: bytes) -> bool:
    if content_type in {"video/webm", "audio/webm"}:
        return prefix.startswith(b"\x1a\x45\xdf\xa3")
    if content_type in {"video/mp4", "video/quicktime"}:
        marker_position = prefix.find(b"ftyp")
        return 4 <= marker_position <= 32
    return False


async def save_video_upload(
    upload: UploadFile,
    upload_dir: Path,
    allowed_video_types: tuple[str, ...],
    max_size_bytes: int,
) -> SavedUpload:
    """Stream an uploaded video to a generated path while enforcing a size limit."""

    content_type = normalize_content_type(upload.content_type)
    normalized_allowed_types = {item.lower() for item in allowed_video_types}
    if content_type not in normalized_allowed_types:
        await upload.close()
        raise InvalidFileTypeError(
            "Поддерживаются только WebM, MP4 и MOV записи."
        )

    extension = CONTENT_TYPE_EXTENSIONS.get(content_type, ".video")
    stored_filename = f"{uuid4().hex}{extension}"
    original_filename = Path(upload.filename or f"recording{extension}").name[:255]
    upload_dir.mkdir(parents=True, exist_ok=True)
    target_path = upload_dir / stored_filename
    size_bytes = 0
    file_prefix = bytearray()

    try:
        with target_path.open("xb") as target_file:
            while chunk := await upload.read(1024 * 1024):
                if len(file_prefix) < 64:
                    file_prefix.extend(chunk[: 64 - len(file_prefix)])
                size_bytes += len(chunk)
                if size_bytes > max_size_bytes:
                    raise FileTooLargeError(
                        "Размер видео превышает максимально допустимый."
                    )
                target_file.write(chunk)

        if size_bytes == 0:
            raise EmptyFileError("Загруженный видеофайл пуст.")
        if not has_expected_container_signature(content_type, bytes(file_prefix)):
            raise InvalidMediaContainerError(
                "Содержимое файла не соответствует заявленному видеоформату."
            )
    except Exception:
        target_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    return SavedUpload(
        original_filename=original_filename,
        stored_filename=stored_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        path=target_path,
    )
