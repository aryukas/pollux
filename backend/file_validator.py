from pathlib import Path

from fastapi import HTTPException, UploadFile

from config import settings


def validate_file_extension(file: UploadFile) -> None:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in settings.allowed_extensions:
        allowed = ", ".join(settings.allowed_extensions)

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types: {allowed}",
        )