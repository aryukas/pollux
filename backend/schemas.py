from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class RootResponse(BaseModel):
    name: str
    status: str
    version: str


class UploadResponse(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    status: str