"""Unit tests for app.db — all DB interactions mocked."""

from unittest.mock import MagicMock, patch


def _mock_session():
    session = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)
    return session, ctx


class TestUpsertModel:
    def test_upsert_model_executes(self):
        session, ctx = _mock_session()
        with (
            patch("app.db.session_scope", return_value=ctx),
            patch("app.db.pg_insert") as mock_insert,
        ):
            mock_insert.return_value.on_conflict_do_update.return_value = MagicMock()
            from app.db import upsert_model

            upsert_model("model-001", "yolo11s")
        session.execute.assert_called_once()


class TestUpsertModelVersion:
    def test_upsert_model_version_executes(self):
        session, ctx = _mock_session()
        with (
            patch("app.db.session_scope", return_value=ctx),
            patch("app.db.pg_insert") as mock_insert,
        ):
            mock_insert.return_value.on_conflict_do_update.return_value = MagicMock()
            from app.db import upsert_model_version

            upsert_model_version(
                model_id="model-001",
                version="1.0.0",
                artifact_uri="gs://bucket/best.pt",
                metadata_uri=None,
                metrics={"mAP": 0.8},
                status="active",
            )
        session.execute.assert_called_once()


class TestListLatestModels:
    def test_returns_list_of_dicts(self):
        session, ctx = _mock_session()
        session.execute.return_value.mappings.return_value.all.return_value = [{"model_id": "m1"}]

        with (
            patch("app.db.session_scope", return_value=ctx),
            patch("app.db.select"),
        ):
            from app.db import list_latest_models

            result = list_latest_models()
        assert isinstance(result, list)
        assert result[0]["model_id"] == "m1"

    def test_returns_empty_list_when_no_rows(self):
        session, ctx = _mock_session()
        session.execute.return_value.mappings.return_value.all.return_value = []

        with (
            patch("app.db.session_scope", return_value=ctx),
            patch("app.db.select"),
        ):
            from app.db import list_latest_models

            result = list_latest_models()
        assert result == []


class TestGetLatestModel:
    def test_returns_dict_when_found(self):
        session, ctx = _mock_session()
        session.execute.return_value.mappings.return_value.first.return_value = {
            "model_id": "m1",
            "status": "active",
        }

        with (
            patch("app.db.session_scope", return_value=ctx),
            patch("app.db.select"),
        ):
            from app.db import get_latest_model

            result = get_latest_model("m1")
        assert result == {"model_id": "m1", "status": "active"}

    def test_returns_none_when_not_found(self):
        session, ctx = _mock_session()
        session.execute.return_value.mappings.return_value.first.return_value = None

        with (
            patch("app.db.session_scope", return_value=ctx),
            patch("app.db.select"),
        ):
            from app.db import get_latest_model

            result = get_latest_model("nonexistent")
        assert result is None


class TestDeleteModel:
    def test_returns_true_when_deleted(self):
        session, ctx = _mock_session()
        session.execute.return_value.rowcount = 1

        with (
            patch("app.db.session_scope", return_value=ctx),
            patch("app.db.delete"),
        ):
            from app.db import delete_model

            result = delete_model("m1")
        assert result is True

    def test_returns_false_when_not_found(self):
        session, ctx = _mock_session()
        session.execute.return_value.rowcount = 0

        with (
            patch("app.db.session_scope", return_value=ctx),
            patch("app.db.delete"),
        ):
            from app.db import delete_model

            result = delete_model("nonexistent")
        assert result is False
