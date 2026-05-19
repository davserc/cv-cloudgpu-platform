from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


class TrainRequest(BaseModel):
    job_id: str | None = Field(default=None, examples=["job-123"])
    config: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Two-phase training config. Required keys: model, name, project, and one dataset source "
            "(train_dataset_url or dataset_gs_uri). Other keys are optional overrides."
        ),
        examples=[
            {
                "dataset_gs_uri": "gs://dataset-unlu-module-4/taco_yolo_13_seg.zip",
                "install_gsutil": True,
                "model": "yolo11s.pt",
                "name": "exp_2fases",
                "project": "runs",
                "device": "0",
                "save": True,
                "ph1_epochs": 25,
                "ph1_patience": 25,
                "ph1_imgsz": 896,
                "ph1_batch": -1,
                "ph1_workers": 4,
                "ph1_freeze": 10,
                "ph1_lr0": 0.01,
                "ph1_lrf": 0.01,
                "ph1_mosaic": 0.7,
                "ph1_close_mosaic": 10,
                "ph1_degrees": 8,
                "ph1_translate": 0.08,
                "ph1_aug_scale": 0.35,
                "ph1_fliplr": 0.5,
                "ph1_copy_paste": 0.4,
                "ph1_cls": 1.0,
                "ph1_erasing": 0.1,
                "ph1_class_weights_auto": 1,
                "ph1_class_weights_power": 0.5,
                "ph1_per_class_metrics": 1,
                "ph1_save_period": 5,
                "ph2_epochs": 100,
                "ph2_patience": 20,
                "ph2_imgsz": 896,
                "ph2_batch": -1,
                "ph2_workers": 4,
                "ph2_freeze": 0,
                "ph2_lr0": 0.002,
                "ph2_lrf": 0.01,
                "ph2_mosaic": 0.7,
                "ph2_close_mosaic": 15,
                "ph2_degrees": 8,
                "ph2_translate": 0.08,
                "ph2_aug_scale": 0.35,
                "ph2_fliplr": 0.5,
                "ph2_copy_paste": 0.6,
                "ph2_cls": 1.0,
                "ph2_erasing": 0.1,
                "ph2_class_weights_auto": 1,
                "ph2_class_weights_power": 0.7,
                "ph2_per_class_metrics": 1,
                "ph2_save_period": 3,
                "ph2_dropout": 0.2,
                "ph2_cos_lr": 1,
                "ph2_focal_loss": 1,
                "ph2_focal_gamma": 1.5,
            }
        ],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "job-2fases-001",
                "config": {
                    "dataset_gs_uri": "gs://dataset-unlu-module-4/taco_yolo_13_seg.zip",
                    "install_gsutil": True,
                    "model": "yolo11s.pt",
                    "name": "exp_2fases",
                    "project": "runs",
                    "device": "0",
                    "ph1_epochs": 25,
                    "ph2_epochs": 100,
                    "ph1_imgsz": 896,
                    "ph2_imgsz": 896,
                    "ph1_batch": -1,
                    "ph2_batch": -1,
                    "ph1_workers": 4,
                    "ph2_workers": 4,
                    "ph1_freeze": 10,
                    "ph2_freeze": 0,
                    "ph1_lr0": 0.01,
                    "ph2_lr0": 0.002,
                    "ph2_cos_lr": 1,
                    "ph2_focal_loss": 0,
                },
            }
        }
    }


class TrainResponse(BaseModel):
    status: str = Field(..., examples=["queued"])
    job_id: str = Field(..., examples=["job-123"])


class TrainLogResponse(BaseModel):
    job_id: str
    log: str
    available: bool


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
