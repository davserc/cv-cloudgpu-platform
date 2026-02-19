from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


class ModelCreateRequest(BaseModel):
    name: str = Field(..., examples=["yolo-v8"])
    version: str = Field(..., examples=["1.0.0"])
    model_id: str | None = Field(default=None, examples=["model-123"])
    artifact_uri: str | None = Field(default=None, examples=["gs://bucket/models/yolo11s/model-123/best.pt"])
    metadata_uri: str | None = Field(default=None, examples=["gs://bucket/models/yolo11s/model-123/metadata.json"])
    job_id: str | None = Field(default=None, examples=["job-123"])
    metrics: dict | None = None
    status: str | None = Field(default="registered", examples=["registered"])


class ModelResponse(BaseModel):
    model_id: str = Field(..., examples=["model-123"])
    status: str = Field(..., examples=["registered"])
    name: str | None = None
    version: str | None = None
    artifact_uri: str | None = None
    metadata_uri: str | None = None
    job_id: str | None = None
    metrics: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ModelListResponse(BaseModel):
    items: list[ModelResponse] = Field(default_factory=list)


class ModelUpdateRequest(BaseModel):
    status: str | None = Field(default=None, examples=["active"])
    metrics: dict | None = None
    metadata_uri: str | None = None


class ModelDeleteResponse(BaseModel):
    status: str = Field(..., examples=["deleted"])
    model_id: str = Field(..., examples=["model-123"])
    deleted: bool = Field(..., examples=[True])
