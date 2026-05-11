from unittest.mock import patch


class TestListModels:
    def test_returns_empty_list(self, client):
        with patch("app.api.v1.routes_models.list_latest_models", return_value=[]):
            resp = client.get("/api/v1/models/")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_returns_models(self, client, sample_model):
        with patch("app.api.v1.routes_models.list_latest_models", return_value=[sample_model]):
            resp = client.get("/api/v1/models/")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["model_id"] == "model-001"


class TestGetModel:
    def test_returns_model(self, client, sample_model):
        with patch("app.api.v1.routes_models.get_latest_model", return_value=sample_model):
            resp = client.get("/api/v1/models/model-001")
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "model-001"

    def test_returns_404_when_not_found(self, client):
        with patch("app.api.v1.routes_models.get_latest_model", return_value=None):
            resp = client.get("/api/v1/models/nonexistent")
        assert resp.status_code == 404


class TestRegisterModel:
    def test_creates_model(self, client, sample_model):
        with (
            patch("app.api.v1.routes_models.upsert_model"),
            patch("app.api.v1.routes_models.upsert_model_version"),
            patch("app.api.v1.routes_models.get_latest_model", return_value=sample_model),
        ):
            resp = client.post(
                "/api/v1/models/",
                json={
                    "model_id": "model-001",
                    "name": "yolo11s",
                    "version": "1.0.0",
                    "artifact_uri": "gs://bucket/best.pt",
                    "status": "registered",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "model-001"

    def test_returns_500_when_db_fails(self, client):
        with (
            patch("app.api.v1.routes_models.upsert_model"),
            patch("app.api.v1.routes_models.upsert_model_version"),
            patch("app.api.v1.routes_models.get_latest_model", return_value=None),
        ):
            resp = client.post(
                "/api/v1/models/",
                json={
                    "name": "test",
                    "version": "1.0",
                    "artifact_uri": "gs://b/m.pt",
                },
            )
        assert resp.status_code == 500


class TestUpdateModel:
    def test_updates_model(self, client, sample_model):
        updated = {**sample_model, "status": "active"}
        with patch("app.api.v1.routes_models.update_latest_model", return_value=updated):
            resp = client.patch("/api/v1/models/model-001", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_returns_404_when_not_found(self, client):
        with patch("app.api.v1.routes_models.update_latest_model", return_value=None):
            resp = client.patch("/api/v1/models/nonexistent", json={"status": "active"})
        assert resp.status_code == 404


class TestDeleteModel:
    def test_deletes_model(self, client):
        with patch("app.api.v1.routes_models.delete_model", return_value=True):
            resp = client.delete("/api/v1/models/model-001")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_returns_404_when_not_found(self, client):
        with patch("app.api.v1.routes_models.delete_model", return_value=False):
            resp = client.delete("/api/v1/models/nonexistent")
        assert resp.status_code == 404
