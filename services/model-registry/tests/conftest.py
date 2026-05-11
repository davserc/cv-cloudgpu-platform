import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub common.db and sqlalchemy before importing app
sys.modules.setdefault("common", MagicMock())
sys.modules.setdefault("common.db", MagicMock())

from fastapi.testclient import TestClient  # noqa: E402

MODEL_ROW = {
    "model_id": "model-001",
    "name": "yolo11s",
    "version": "1.0.0",
    "artifact_uri": "gs://bucket/best.pt",
    "metadata_uri": None,
    "metrics": {"mAP": 0.75},
    "status": "active",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
}


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def sample_model():
    return MODEL_ROW.copy()
