import os
import sys
from unittest.mock import MagicMock

# Stub contracts before import
sys.modules.setdefault("contracts", MagicMock())
sys.modules.setdefault("contracts.events", MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.training import build_run_cmd, model_base_name, resolve_artifact_src  # noqa: E402


def _make_event(config=None, job_id="job-001"):
    event = MagicMock()
    event.job_id = job_id
    event.config = config or {}
    return event


class TestModelBaseName:
    def test_strips_extension(self):
        assert model_base_name("yolo11s.pt") == "yolo11s"

    def test_no_extension(self):
        assert model_base_name("yolo11s") == "yolo11s"

    def test_full_path(self):
        assert model_base_name("/models/yolo11s.pt") == "yolo11s"


class TestBuildRunCmd:
    def test_two_phase_mode_default(self, monkeypatch):
        monkeypatch.setenv("TRAIN_MODE", "two_phase")
        monkeypatch.delenv("TRAIN_RUN_CMD", raising=False)
        event = _make_event({"dataset_name": "taco"})
        cmd = build_run_cmd(event)
        assert "bash /work/run_service.sh" in cmd

    def test_uses_override_when_set(self, monkeypatch):
        monkeypatch.setenv("TRAIN_RUN_CMD", "python train.py")
        cmd = build_run_cmd(_make_event())
        assert cmd == "python train.py"

    def test_two_phase_includes_ph1_epochs(self, monkeypatch):
        monkeypatch.setenv("TRAIN_MODE", "two_phase")
        monkeypatch.delenv("TRAIN_RUN_CMD", raising=False)
        event = _make_event({"ph1_epochs": 5})
        cmd = build_run_cmd(event)
        assert "PH1_EPOCHS=5" in cmd

    def test_yolo_mode(self, monkeypatch):
        monkeypatch.setenv("TRAIN_MODE", "yolo")
        monkeypatch.delenv("TRAIN_RUN_CMD", raising=False)
        event = _make_event()
        cmd = build_run_cmd(event)
        assert "yolo train" in cmd

    def test_config_overrides_env(self, monkeypatch):
        monkeypatch.setenv("TRAIN_MODE", "two_phase")
        monkeypatch.delenv("TRAIN_RUN_CMD", raising=False)
        monkeypatch.setenv("MODEL_SCALE", "s")
        event = _make_event({"model_scale": "l"})
        cmd = build_run_cmd(event)
        assert "MODEL_SCALE=l" in cmd


class TestResolveArtifactSrc:
    def test_two_phase_default_path(self, monkeypatch):
        monkeypatch.setenv("TRAIN_MODE", "two_phase")
        monkeypatch.delenv("TRAIN_ARTIFACT_SRC", raising=False)
        event = _make_event(job_id="job-abc")
        srcs = resolve_artifact_src(event)
        assert isinstance(srcs, list)
        assert any("/work/runs/segment/" in s for s in srcs)
        assert any("best.pt" in s for s in srcs)
        assert any("last.pt" in s for s in srcs)

    def test_uses_override(self, monkeypatch):
        monkeypatch.setenv("TRAIN_ARTIFACT_SRC", "/custom/path/best.pt")
        srcs = resolve_artifact_src(_make_event())
        assert srcs == ["/custom/path/best.pt"]

    def test_ph2_name_in_path(self, monkeypatch):
        monkeypatch.setenv("TRAIN_MODE", "two_phase")
        monkeypatch.delenv("TRAIN_ARTIFACT_SRC", raising=False)
        event = _make_event({"ph2_name": "my_ph2"})
        srcs = resolve_artifact_src(event)
        assert all("my_ph2" in s for s in srcs)

    def test_yolo_mode_path(self, monkeypatch):
        monkeypatch.setenv("TRAIN_MODE", "yolo")
        monkeypatch.delenv("TRAIN_ARTIFACT_SRC", raising=False)
        event = _make_event({"name": "my_exp", "project": "runs"})
        srcs = resolve_artifact_src(event)
        assert all("my_exp" in s for s in srcs)
        assert any("best.pt" in s for s in srcs)
        assert any("last.pt" in s for s in srcs)
