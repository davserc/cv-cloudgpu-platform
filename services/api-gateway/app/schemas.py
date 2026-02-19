from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


class TrainRequest(BaseModel):
    job_id: str | None = Field(default=None, examples=["job-123"])
    batch: int = Field(..., examples=[8])
    device: str = Field(..., examples=["0"])
    epochs: int = Field(..., examples=[1])
    imgsz: int = Field(..., examples=[640])
    model: str = Field(..., examples=["yolo11s.pt"])
    name: str = Field(..., examples=["exp_1"])
    patience: int = Field(..., examples=[50])
    project: str = Field(..., examples=["runs"])
    save: bool = Field(..., examples=[True])

    model_config = {
        "json_schema_extra": {
            "example": {
                "batch": 8,
                "device": "0",
                "epochs": 1,
                "imgsz": 640,
                "model": "yolo11s.pt",
                "name": "exp_1",
                "patience": 50,
                "project": "runs",
                "save": True,
            }
        }
    }


class TrainResponse(BaseModel):
    status: str = Field(..., examples=["queued"])
    job_id: str = Field(..., examples=["job-123"])


class ModelSummary(BaseModel):
    model_id: str
    status: str | None = None


class ModelsListResponse(BaseModel):
    items: list[ModelSummary] = Field(default_factory=list)


class ModelDeleteResponse(BaseModel):
    status: str = Field(..., examples=["deleted"])
    model_id: str = Field(..., examples=["model-123"])
    deleted: bool = Field(..., examples=[True])


class InferRequest(BaseModel):
    model_id: str | None = None
    inputs: list[str] = Field(default_factory=list, examples=[["s3://bucket/images/img1.jpg"]])


class InferResponse(BaseModel):
    predictions: list[dict] = Field(default_factory=list)
