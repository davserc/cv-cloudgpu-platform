from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


class JobCreateRequest(BaseModel):
    dataset_uri: str = Field(..., examples=["s3://bucket/datasets/train"])
    config: dict[str, Any] | None = None


class JobStatusResponse(BaseModel):
    job_id: str = Field(..., examples=["job-123"])
    status: str = Field(..., examples=["queued"])
