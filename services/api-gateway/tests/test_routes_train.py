import pytest
from unittest.mock import MagicMock, patch, ANY
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, api_key):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    monkeypatch.setenv("KAFKA_TOPIC", "training-jobs")

    with patch("app.api.v1.routes_train.build_producer") as mock_prod, \
         patch("app.api.v1.routes_train.session_scope") as mock_scope:
        mock_producer = MagicMock()
        mock_prod.return_value = mock_producer
        mock_scope.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)

        from app.main import app
        yield TestClient(app), api_key, mock_producer


def test_submit_job_returns_queued(client):
    tc, key, mock_producer = client
    resp = tc.post(
        "/api/v1/train/",
        json={"config": {"model": "yolo11s.pt"}},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert "job_id" in data


def test_submit_job_uses_provided_job_id(client):
    tc, key, _ = client
    resp = tc.post(
        "/api/v1/train/",
        json={"job_id": "my-job-123", "config": {}},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 200
    assert resp.json()["job_id"] == "my-job-123"


def test_submit_job_sends_to_kafka(client):
    tc, key, mock_producer = client
    tc.post(
        "/api/v1/train/",
        json={"config": {}},
        headers={"X-API-Key": key},
    )
    mock_producer.send.assert_called_once()


def test_submit_job_requires_api_key(client):
    tc, _, _ = client
    resp = tc.post("/api/v1/train/", json={"config": {}})
    assert resp.status_code == 401


def test_submit_job_rejects_wrong_key(client):
    tc, _, _ = client
    resp = tc.post(
        "/api/v1/train/",
        json={"config": {}},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 403
