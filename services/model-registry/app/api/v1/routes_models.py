from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.db import (
    delete_model,
    get_latest_model,
    list_latest_models,
    update_latest_model,
    upsert_model,
    upsert_model_version,
)
from app.schemas import (
    ModelCreateRequest,
    ModelDeleteResponse,
    ModelListResponse,
    ModelResponse,
    ModelUpdateRequest,
)

router = APIRouter()


@router.get("/", response_model=ModelListResponse)
def list_models() -> ModelListResponse:
    items = list_latest_models()
    return ModelListResponse(items=[ModelResponse(**item) for item in items])


@router.get("/{model_id}", response_model=ModelResponse)
def get_model(model_id: str) -> ModelResponse:
    item = get_latest_model(model_id)
    if not item:
        raise HTTPException(status_code=404, detail="model not found")
    return ModelResponse(**item)


@router.post("/", response_model=ModelResponse)
def register_model(payload: ModelCreateRequest) -> ModelResponse:
    model_id = payload.model_id or f"model-{uuid4()}"
    upsert_model(model_id, payload.name)
    upsert_model_version(
        model_id=model_id,
        version=payload.version,
        artifact_uri=payload.artifact_uri,
        metadata_uri=payload.metadata_uri,
        metrics=payload.metrics,
        status=payload.status or "registered",
    )
    item = get_latest_model(model_id)
    if not item:
        raise HTTPException(status_code=500, detail="failed to register model")
    return ModelResponse(**item)


@router.patch("/{model_id}", response_model=ModelResponse)
def update_model(model_id: str, payload: ModelUpdateRequest) -> ModelResponse:
    item = update_latest_model(
        model_id,
        status=payload.status,
        metadata_uri=payload.metadata_uri,
        metrics=payload.metrics,
    )
    if not item:
        raise HTTPException(status_code=404, detail="model not found")
    return ModelResponse(**item)


@router.delete("/{model_id}", response_model=ModelDeleteResponse)
def delete_model_by_id(model_id: str) -> ModelDeleteResponse:
    deleted = delete_model(model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="model not found")
    return ModelDeleteResponse(status="deleted", model_id=model_id, deleted=True)
