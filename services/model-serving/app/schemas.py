from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


class InferRequest(BaseModel):
    model_id: str | None = None
    inputs: list[str] = Field(default_factory=list, examples=[["s3://bucket/images/img1.jpg"]])


class InferResponse(BaseModel):
    predictions: list[dict[str, Any]] = Field(default_factory=list)


class ModelInfoResponse(BaseModel):
    model_id: str | None = None
    status: str | None = None
    name: str | None = None
    version: str | None = None
    artifact_uri: str | None = None
    metadata_uri: str | None = None
    job_id: str | None = None
    metrics: dict | None = None
