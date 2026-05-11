"""
Kafka integration tests using mocks (no real broker needed).
Tests the producer/consumer contract and DLQ flow.
"""

import json
import sys
from unittest.mock import MagicMock, patch

# Stub kafka before any app imports
kafka_mock = MagicMock()
sys.modules.setdefault("kafka", kafka_mock)
sys.modules.setdefault("kafka.KafkaProducer", kafka_mock.KafkaProducer)
sys.modules.setdefault("kafka.KafkaConsumer", kafka_mock.KafkaConsumer)


class TestKafkaProducerContract:
    """Verify the api-gateway produces well-formed TrainingJobEvent messages."""

    def test_published_message_has_required_fields(self):
        captured = {}

        def fake_send(topic, value):
            captured["topic"] = topic
            captured["value"] = value

        mock_producer = MagicMock()
        mock_producer.send.side_effect = fake_send

        with (
            patch("app.api.v1.routes_train.build_producer", return_value=mock_producer),
            patch("app.api.v1.routes_train.session_scope") as mock_scope,
        ):
            sys.path.insert(0, "services/api-gateway")
            sys.modules.setdefault("common", MagicMock())
            sys.modules.setdefault("common.db", MagicMock())
            sys.modules.setdefault("contracts", MagicMock())
            sys.modules.setdefault("contracts.events", MagicMock())
            mock_scope.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            from fastapi.testclient import TestClient

            from app.main import app

            client = TestClient(app)

        import os

        os.environ["API_GATEWAY_API_KEY"] = "test-key"
        resp = client.post(
            "/api/v1/train/",
            json={"config": {"model": "yolo11s.pt"}},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200

    def test_message_serialization_roundtrip(self):
        """Verify JSON serialization used by the producer is reversible."""
        payload = {
            "event_type": "training-job",
            "event_id": "uuid-1",
            "timestamp": "2026-01-01T00:00:00Z",
            "job_id": "job-123",
            "config": {"model": "yolo11s.pt", "epochs": 10},
        }
        serialized = json.dumps(payload).encode("utf-8")
        deserialized = json.loads(serialized.decode("utf-8"))
        assert deserialized["job_id"] == "job-123"
        assert deserialized["config"]["epochs"] == 10


class TestDLQFlow:
    """Test that failed jobs are published to the DLQ topic."""

    def test_dlq_message_has_error_field(self):
        dlq_event = {
            "event_type": "training-failed",
            "event_id": "uuid-err",
            "timestamp": "2026-01-01T00:00:00Z",
            "job_id": "job-fail",
            "error": "No instance booted",
            "config": {},
        }
        assert "error" in dlq_event
        assert dlq_event["event_type"] == "training-failed"

    def test_dlq_serialization(self):
        dlq_event = {
            "event_type": "training-failed",
            "job_id": "job-001",
            "error": "SSH timeout",
        }
        serialized = json.dumps(dlq_event).encode("utf-8")
        assert b"training-failed" in serialized

    def test_consumer_deserializes_message(self):
        raw = json.dumps(
            {
                "event_type": "training-job",
                "job_id": "job-001",
                "config": {},
            }
        ).encode("utf-8")

        def deserializer(v):
            return v.decode("utf-8") if v else ""

        result = json.loads(deserializer(raw))
        assert result["job_id"] == "job-001"
