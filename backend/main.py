from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from file_validator import (
    validate_content_type,
    validate_file_extension,
    validate_file_signature,
    validate_image,
    validate_pdf,
)
from schemas import (
    HealthResponse,
    RootResponse,
    UploadResponse,
)


app = FastAPI(
    title=settings.app_name,
    description="Cash Flow Statement Extraction API",
    version=settings.app_version,
)


# Allow requests from the local React/Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=RootResponse)
def root():
    return RootResponse(
        name=settings.app_name,
        status="running",
        version=settings.app_version,
    )


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="healthy",
    )


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    # 1. Validate file extension
    extension = validate_file_extension(file)

    # 2. Validate MIME/content type
    validate_content_type(file, extension)

    # 3. Read uploaded file into memory
    content = await file.read()

    # 4. Reject empty files
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    # 5. Validate maximum file size
    max_size = settings.max_upload_size_mb * 1024 * 1024

    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File exceeds the maximum size of "
                f"{settings.max_upload_size_mb} MB."
            ),
        )

    # 6. Validate actual file signature
    validate_file_signature(content, extension)

    # 7. Validate actual image/PDF structure
    if extension in {".jpg", ".jpeg", ".png"}:
        validate_image(content)

    elif extension == ".pdf":
        validate_pdf(content)

    # 8. Return successful upload response
    return UploadResponse(
        filename=file.filename or "unknown",
        content_type=file.content_type or "unknown",
        size_bytes=len(content),
        status="accepted",
    )