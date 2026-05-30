import io
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.model_store import (
    _download_gcs,
    _download_http,
    download_artifact_to_cache,
    get_model_entry,
    pick_default_model,
)
from app.schemas import InferRequest, InferResponse, ModelInfoResponse
from common.db import inference_requests, inference_results, model_versions, session_scope

router = APIRouter()

_model_cache: dict[str, Any] = {}
_model_lock = threading.RLock()
_active_model_entry: dict[str, Any] | None = None


def clear_model_cache() -> None:
    with _model_lock:
        _model_cache.clear()


def get_active_model_entry() -> dict[str, Any] | None:
    with _model_lock:
        return _active_model_entry.copy() if _active_model_entry else None


def _load_model(model_id: str, artifact_uri: str):
    with _model_lock:
        cached = _model_cache.get(model_id)
    if cached is not None:
        return cached
    try:
        from ultralytics import YOLO  # type: ignore
    except Exception as exc:
        raise RuntimeError("ultralytics not available") from exc

    cache_dir = Path(os.getenv("MODEL_CACHE_DIR", "/data/models"))
    model_path = download_artifact_to_cache(artifact_uri, cache_dir)
    model = YOLO(str(model_path))
    with _model_lock:
        _model_cache[model_id] = model
    return model


def _load_model_uncached(artifact_uri: str):
    try:
        from ultralytics import YOLO  # type: ignore
    except Exception as exc:
        raise RuntimeError("ultralytics not available") from exc

    cache_dir = Path(os.getenv("MODEL_CACHE_DIR", "/data/models"))
    model_path = download_artifact_to_cache(artifact_uri, cache_dir)
    return YOLO(str(model_path))


def swap_active_model(model_entry: dict[str, Any]) -> None:
    artifact_uri = model_entry.get("artifact_uri")
    model_id = model_entry.get("model_id")
    if not artifact_uri or not model_id:
        raise ValueError("model_entry missing artifact_uri or model_id")

    new_model = _load_model_uncached(artifact_uri)
    with _model_lock:
        _model_cache.clear()
        _model_cache[model_id] = new_model
        global _active_model_entry
        _active_model_entry = model_entry.copy()


def _prepare_input(uri: str) -> str:
    if uri.startswith("gs://") or uri.startswith("http://") or uri.startswith("https://"):
        tmp_dir = Path(tempfile.mkdtemp(prefix="infer_"))
        filename = Path(uri).name or "input"
        dst = tmp_dir / filename
        # reuse download logic from model_store for gs/http
        if uri.startswith("gs://"):
            _download_gcs(uri, dst)
        else:
            _download_http(uri, dst)
        return str(dst)
    return uri


def _results_to_dict(results) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for res in results:
        boxes_out = []
        if res.boxes is not None:
            for box in res.boxes:
                xyxy = box.xyxy[0].tolist()
                conf = float(box.conf[0]) if box.conf is not None else None
                cls = int(box.cls[0]) if box.cls is not None else None
                name = res.names.get(cls) if cls is not None else None
                boxes_out.append(
                    {
                        "xyxy": xyxy,
                        "conf": conf,
                        "class": cls,
                        "name": name,
                    }
                )
        outputs.append({"boxes": boxes_out})
    return outputs


def _annotate_image(image_path: str, results) -> bytes:
    # Use YOLO's built-in plot() which scales labels and boxes correctly
    # regardless of the original image resolution.
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError("pillow/numpy not available") from exc

    annotated_bgr = results[0].plot()  # ndarray BGR
    img_pil = Image.fromarray(annotated_bgr[..., ::-1])  # BGR → RGB

    buf = io.BytesIO()
    img_pil.save(buf, format="PNG")
    return buf.getvalue()


def _latest_model_version_id(model_id: str) -> int | None:
    stmt = (
        select(model_versions.c.id)
        .where(model_versions.c.model_id == model_id)
        .order_by(model_versions.c.updated_at.desc())
        .limit(1)
    )
    with session_scope() as session:
        return session.execute(stmt).scalar()


@router.get("/model", response_model=ModelInfoResponse)
def get_active_model(model_id: str | None = None) -> ModelInfoResponse:
    if model_id:
        model_entry = get_model_entry(model_id)
    else:
        model_entry = get_active_model_entry() or pick_default_model()
    if not model_entry:
        raise HTTPException(status_code=404, detail="model not found")
    return ModelInfoResponse(**model_entry)


@router.post("/", response_model=InferResponse)
def infer(payload: InferRequest) -> InferResponse:
    if not payload.inputs:
        raise HTTPException(status_code=400, detail="inputs is required")

    started = time.time()
    request_id = str(uuid4())

    model_entry = None
    if payload.model_id:
        model_entry = get_model_entry(payload.model_id)
    if model_entry is None:
        model_entry = get_active_model_entry() or pick_default_model()

    if not model_entry:
        raise HTTPException(status_code=404, detail="model not found")

    artifact_uri = model_entry.get("artifact_uri")
    if not artifact_uri:
        raise HTTPException(status_code=404, detail="artifact_uri not found for model")

    model_id = model_entry.get("model_id")
    version_id = _latest_model_version_id(model_id) if model_id else None

    with session_scope() as session:
        session.execute(
            pg_insert(inference_requests).values(
                request_id=request_id,
                model_id=model_id,
                model_version_id=version_id,
                inputs_json=payload.inputs,
                status="started",
            )
        )
    model = _load_model(model_id, artifact_uri)

    preds: list[dict[str, Any]] = []
    try:
        for uri in payload.inputs:
            src = _prepare_input(uri)
            results = model.predict(source=src, save=False, verbose=False)
            preds.append(
                {
                    "input": uri,
                    "results": _results_to_dict(results),
                }
            )
        latency_ms = int((time.time() - started) * 1000)
        with session_scope() as session:
            session.execute(
                update(inference_requests)
                .where(inference_requests.c.request_id == request_id)
                .values(status="succeeded", latency_ms=latency_ms)
            )
            session.execute(
                pg_insert(inference_results).values(
                    request_id=select(inference_requests.c.id)
                    .where(inference_requests.c.request_id == request_id)
                    .scalar_subquery(),
                    outputs_json=preds,
                )
            )
        return InferResponse(predictions=preds)
    except Exception:
        latency_ms = int((time.time() - started) * 1000)
        with session_scope() as session:
            session.execute(
                update(inference_requests)
                .where(inference_requests.c.request_id == request_id)
                .values(status="failed", latency_ms=latency_ms)
            )
        raise


@router.post("/annotated")
def infer_annotated(payload: InferRequest) -> Response:
    if not payload.inputs:
        raise HTTPException(status_code=400, detail="inputs is required")

    started = time.time()
    request_id = str(uuid4())

    model_entry = None
    if payload.model_id:
        model_entry = get_model_entry(payload.model_id)
    if model_entry is None:
        model_entry = get_active_model_entry() or pick_default_model()

    if not model_entry:
        raise HTTPException(status_code=404, detail="model not found")

    artifact_uri = model_entry.get("artifact_uri")
    if not artifact_uri:
        raise HTTPException(status_code=404, detail="artifact_uri not found for model")

    model_id = model_entry.get("model_id")
    version_id = _latest_model_version_id(model_id) if model_id else None
    with session_scope() as session:
        session.execute(
            pg_insert(inference_requests).values(
                request_id=request_id,
                model_id=model_id,
                model_version_id=version_id,
                inputs_json=payload.inputs,
                status="started",
            )
        )
    model = _load_model(model_id, artifact_uri)

    try:
        src = _prepare_input(payload.inputs[0])
        results = model.predict(source=src, save=False, verbose=False)
        img_bytes = _annotate_image(src, results)
        latency_ms = int((time.time() - started) * 1000)
        with session_scope() as session:
            session.execute(
                update(inference_requests)
                .where(inference_requests.c.request_id == request_id)
                .values(status="succeeded", latency_ms=latency_ms)
            )
            session.execute(
                pg_insert(inference_results).values(
                    request_id=select(inference_requests.c.id)
                    .where(inference_requests.c.request_id == request_id)
                    .scalar_subquery(),
                    outputs_json=_results_to_dict(results),
                )
            )
        return Response(content=img_bytes, media_type="image/png")
    except Exception:
        latency_ms = int((time.time() - started) * 1000)
        with session_scope() as session:
            session.execute(
                update(inference_requests)
                .where(inference_requests.c.request_id == request_id)
                .values(status="failed", latency_ms=latency_ms)
            )
        raise
