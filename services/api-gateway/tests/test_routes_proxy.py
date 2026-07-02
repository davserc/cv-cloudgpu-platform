"""Tests for api-gateway proxy routes (models and infer)."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(api_key):
    from app.main import app

    return TestClient(app), api_key


def _mock_urlopen(body: bytes):
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ── /api/v1/models ──────────────────────────────────────────────────────────


def test_list_models_returns_items(client):
    tc, key = client
    body = json.dumps({"items": [{"model_id": "m1", "status": "active"}]}).encode()
    with patch("app.api.v1.routes_models.request.urlopen", return_value=_mock_urlopen(body)):
        resp = tc.get("/api/v1/models/", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["model_id"] == "m1"


def test_list_models_requires_auth(client):
    tc, _ = client
    resp = tc.get("/api/v1/models/")
    assert resp.status_code == 401


def test_get_model_returns_model(client):
    tc, key = client
    body = json.dumps({"model_id": "m1", "status": "active"}).encode()
    with patch("app.api.v1.routes_models.request.urlopen", return_value=_mock_urlopen(body)):
        resp = tc.get("/api/v1/models/m1", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["model_id"] == "m1"


def test_delete_model_proxies(client):
    tc, key = client
    body = json.dumps({"status": "deleted", "model_id": "m1", "deleted": True}).encode()
    with patch("app.api.v1.routes_models.request.urlopen", return_value=_mock_urlopen(body)):
        resp = tc.delete("/api/v1/models/m1", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_list_models_upstream_error(client):
    tc, key = client
    with patch(
        "app.api.v1.routes_models.request.urlopen", side_effect=OSError("connection refused")
    ):
        resp = tc.get("/api/v1/models/", headers={"X-API-Key": key})
    assert resp.status_code == 502


# ── /api/v1/infer ───────────────────────────────────────────────────────────


def test_infer_get_model_upstream_error_returns_502(client):
    tc, key = client
    with patch(
        "app.api.v1.routes_infer.request.urlopen", side_effect=OSError("connection refused")
    ):
        resp = tc.get("/api/v1/infer/model", headers={"X-API-Key": key})
    assert resp.status_code == 502


def test_infer_requires_auth(client):
    tc, _ = client
    resp = tc.get("/api/v1/infer/model")
    assert resp.status_code == 401


def test_infer_upload_sends_gcs_uri_to_serving(client):
    tc, key = client
    body = json.dumps({"predictions": [{"input": "x", "results": []}]}).encode()
    with (
        patch(
            "app.api.v1.routes_infer.upload_bytes_to_gcs",
            return_value="gs://some-bucket/uploads/abc_cat.jpg",
        ) as mock_upload,
        patch(
            "app.api.v1.routes_infer.request.urlopen", return_value=_mock_urlopen(body)
        ) as mock_urlopen,
    ):
        resp = tc.post(
            "/api/v1/infer/upload",
            headers={"X-API-Key": key},
            files={"file": ("cat.jpg", b"fake-bytes", "image/jpeg")},
        )
    assert resp.status_code == 200
    mock_upload.assert_called_once()
    assert mock_upload.call_args.args[0] == b"fake-bytes"
    assert mock_upload.call_args.args[1] == "cat.jpg"
    sent_payload = json.loads(mock_urlopen.call_args.args[0].data)
    assert sent_payload["inputs"] == ["gs://some-bucket/uploads/abc_cat.jpg"]


def test_infer_upload_gcs_failure_returns_502(client):
    tc, key = client
    with patch(
        "app.api.v1.routes_infer.upload_bytes_to_gcs",
        side_effect=RuntimeError("boom"),
    ):
        resp = tc.post(
            "/api/v1/infer/upload",
            headers={"X-API-Key": key},
            files={"file": ("cat.jpg", b"fake-bytes", "image/jpeg")},
        )
    assert resp.status_code == 502


def test_infer_upload_requires_auth(client):
    tc, _ = client
    resp = tc.post(
        "/api/v1/infer/upload",
        files={"file": ("cat.jpg", b"fake-bytes", "image/jpeg")},
    )
    assert resp.status_code == 401
