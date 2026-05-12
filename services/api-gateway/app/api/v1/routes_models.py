import json
import os
from urllib import parse, request

from fastapi import APIRouter, HTTPException

from app.schemas import ModelDeleteResponse, ModelsListResponse, ModelSummary

router = APIRouter()


def _registry_url() -> str:
    return os.getenv("MODEL_REGISTRY_URL", "http://model-registry:8000/api/v1/models")


@router.get(
    "/",
    response_model=ModelsListResponse,
    summary="List models",
    description="Proxy to model-registry and return the models catalog.",
)
def list_models() -> ModelsListResponse:
    req = request.Request(_registry_url(), method="GET")
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            return ModelsListResponse.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/{model_id}",
    response_model=ModelSummary,
    summary="Get model by id",
    description="Proxy to model-registry and return model details.",
)
def get_model(model_id: str) -> ModelSummary:
    url = f"{_registry_url().rstrip('/')}/{parse.quote(model_id)}"
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            return ModelSummary.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete(
    "/{model_id}",
    response_model=ModelDeleteResponse,
    summary="Delete model by id",
    description="Proxy to model-registry and delete a model.",
)
def delete_model(model_id: str) -> ModelDeleteResponse:
    url = f"{_registry_url().rstrip('/')}/{parse.quote(model_id)}"
    req = request.Request(url, method="DELETE")
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body) if body else {}
            return ModelDeleteResponse.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
