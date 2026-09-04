from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image
from pypdf import PdfReader

from config import settings


IMAGE_SIGNATURES = {
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89PNG\r\n\x1a\n",
}

PDF_SIGNATURE = b"%PDF"


def validate_file_extension(file: UploadFile) -> str:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in settings.allowed_extensions:
        allowed = ", ".join(settings.allowed_extensions)

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types: {allowed}",
        )

    return extension


def validate_content_type(file: UploadFile, extension: str) -> None:
    expected_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".pdf": "application/pdf",
    }

    expected = expected_types[extension]

    if file.content_type != expected:
        raise HTTPException(
            status_code=400,
            detail="File extension and content type do not match.",
        )


def validate_file_signature(content: bytes, extension: str) -> None:
    if extension in IMAGE_SIGNATURES:
        signature = IMAGE_SIGNATURES[extension]

        if not content.startswith(signature):
            raise HTTPException(
                status_code=400,
                detail="File content does not match the declared image type.",
            )

    elif extension == ".pdf":
        if not content.startswith(PDF_SIGNATURE):
            raise HTTPException(
                status_code=400,
                detail="File content does not appear to be a valid PDF.",
            )


def validate_image(content: bytes) -> None:
    try:
        from io import BytesIO

        with Image.open(BytesIO(content)) as image:
            image.verify()

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid or corrupted image file.",
        ) from exc


def validate_pdf(content: bytes) -> None:
    try:
        from io import BytesIO

        reader = PdfReader(BytesIO(content))

        page_count = len(reader.pages)

        if page_count == 0:
            raise HTTPException(
                status_code=400,
                detail="PDF contains no pages.",
            )

        if page_count > settings.max_pdf_pages:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"PDF exceeds the maximum allowed "
                    f"page count of {settings.max_pdf_pages}."
                ),
            )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid or corrupted PDF file.",
        ) from exc