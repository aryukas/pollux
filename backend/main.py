from fastapi import FastAPI

from config import settings
from schemas import HealthResponse, RootResponse

app = FastAPI(
    title=settings.app_name,
    description="Cash Flow Statement Extraction API",
    version=settings.app_version,
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
        status="healthy"
    )