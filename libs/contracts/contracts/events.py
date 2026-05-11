from typing import Any

from pydantic import BaseModel, Field


class EventBase(BaseModel):
    event_type: str
    event_id: str = Field(..., description="Unique event id")
    timestamp: str = Field(..., description="ISO-8601 timestamp")


class TrainingJobEvent(EventBase):
    event_type: str = "TRAINING_JOB"
    job_id: str
    config: dict[str, Any] | None = None


class ModelTrainedEvent(EventBase):
    event_type: str = "MODEL_TRAINED"
    job_id: str
    model_id: str
    artifact_uri: str
    metrics: dict[str, Any] | None = None


class ModelEvaluatedEvent(EventBase):
    event_type: str = "MODEL_EVALUATED"
    model_id: str
    report_uri: str
    metrics: dict[str, Any] = Field(default_factory=dict)
