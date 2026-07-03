import json
import os
from pathlib import Path
from urllib import parse, request

from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from app.gcs_utils import upload_bytes_to_gcs
from app.schemas import InferRequest, InferResponse

router = APIRouter()


def _serving_url() -> str:
    return os.getenv("MODEL_SERVING_URL", "http://model-serving:8000/api/v1/infer")


def _infer(payload: InferRequest) -> InferResponse:
    data = json.dumps(payload.model_dump()).encode("utf-8")
    url = _serving_url()
    if not url.endswith("/"):
        url = f"{url}/"
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=170) as resp:
            body = resp.read().decode("utf-8")
            return InferResponse.model_validate_json(body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _infer_annotated(payload: InferRequest):
    data = json.dumps(payload.model_dump()).encode("utf-8")
    base_url = _serving_url().rstrip("/")
    url = f"{base_url}/annotated"
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=170) as resp:
            body = resp.read()
            return Response(content=body, media_type="image/png")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/model",
    summary="Get active model",
    description="Returns the active model entry from model-serving, or a specific model if model_id is provided.",
)
def get_active_model(model_id: str | None = None):
    base_url = _serving_url().rstrip("/")
    url = f"{base_url}/model"
    if model_id:
        url = f"{url}?{parse.urlencode({'model_id': model_id})}"
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/upload",
    response_model=InferResponse,
    summary="Upload image and run inference",
    description="Upload a local image file and receive JSON predictions.",
)
def infer_upload(
    file: UploadFile = File(...),
    model_id: str | None = None,
) -> InferResponse:
    safe_name = Path(file.filename or "input").name
    try:
        gcs_uri = upload_bytes_to_gcs(file.file.read(), safe_name, content_type=file.content_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GCS upload failed: {exc}") from exc

    payload = InferRequest(
        model_id=model_id,
        inputs=[gcs_uri],
    )
    return _infer(payload)


@router.post(
    "/upload/annotated",
    summary="Upload image and return annotated image",
    description="Upload a local image file and receive a PNG with drawn boxes.",
)
def infer_upload_annotated(
    file: UploadFile = File(...),
    model_id: str | None = None,
):
    safe_name = Path(file.filename or "input").name
    try:
        gcs_uri = upload_bytes_to_gcs(file.file.read(), safe_name, content_type=file.content_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GCS upload failed: {exc}") from exc

    payload = InferRequest(
        model_id=model_id,
        inputs=[gcs_uri],
    )
    return _infer_annotated(payload)
