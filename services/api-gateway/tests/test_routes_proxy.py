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
