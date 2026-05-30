from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from contracts.events import TrainingJobEvent

logger = logging.getLogger(__name__)


def model_base_name(model: str) -> str:
    name = Path(model).name
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name


def _cfg(event: TrainingJobEvent, config_key: str, env_key: str, default: Any = None) -> Any:
    """Read from event.config first, then env var, then default."""
    if event.config and isinstance(event.config, dict):
        val = event.config.get(config_key)
        if val is not None:
            return val
    env_val = os.getenv(env_key)
    return env_val if env_val is not None else default


def _checkpoint_gcs_uri(event: TrainingJobEvent) -> str | None:
    base = os.getenv("TRAIN_CHECKPOINT_GCS_BASE_URI")
    if not base:
        return None
    job_id = os.getenv("JOB_ID") or event.job_id
    return f"{base.rstrip('/')}/{job_id}"


def _build_two_phase_cmd(event: TrainingJobEvent) -> str:
    """Invoke run_service.sh on the remote instance with env var overrides."""
    overrides: dict[str, Any] = {}

    overrides["DATASET_NAME"] = _cfg(event, "dataset_name", "DATASET_NAME", "taco_yolo_13_seg")
    dataset_root = _cfg(event, "dataset_root", "DATASET_ROOT")
    if dataset_root:
        overrides["DATASET_ROOT"] = dataset_root
    dataset_yaml = _cfg(event, "data", "DATASET_YAML")
    if dataset_yaml:
        overrides["DATASET_YAML"] = dataset_yaml

    # Extract scale from model name if model_scale not explicitly set.
    # e.g. "yolo11l-seg.pt" → "l", "yolo11x.pt" → "x"
    _model_raw = (event.config or {}).get("model", "")
    _scale_from_name = None
    if _model_raw:
        import re as _re
        _m = _re.search(r"yolo\d+([nsmlx])", str(_model_raw))
        if _m:
            _scale_from_name = _m.group(1)
    overrides["MODEL_SCALE"] = _cfg(event, "model_scale", "MODEL_SCALE", _scale_from_name or "m")
    overrides["WORKERS"] = _cfg(event, "workers", "WORKERS", "4")
    overrides["DEVICE"] = _cfg(event, "device", "DEVICE", "0")

    overrides["RUNS_DIR"] = _cfg(event, "runs_dir", "RUNS_DIR", "/work/runs")
    overrides["CKPT_DIR"] = _cfg(event, "ckpt_dir", "CKPT_DIR", "/work/checkpoints")

    base_name = _cfg(event, "name", "TRAIN_NAME", event.job_id)
    overrides["PH1_NAME"] = _cfg(event, "ph1_name", "PH1_NAME", f"{base_name}_ph1")
    overrides["PH2_NAME"] = _cfg(event, "ph2_name", "PH2_NAME", f"{base_name}_ph2")

    overrides["PH1_EPOCHS"] = _cfg(event, "ph1_epochs", "PH1_EPOCHS", "25")
    overrides["PH1_PATIENCE"] = _cfg(event, "ph1_patience", "PH1_PATIENCE", "25")
    overrides["PH2_EPOCHS"] = _cfg(event, "ph2_epochs", "PH2_EPOCHS", "150")
    overrides["PH2_PATIENCE"] = _cfg(event, "ph2_patience", "PH2_PATIENCE", "40")
    overrides["PH1_IMGSZ"] = _cfg(event, "ph1_imgsz", "PH1_IMGSZ", 896)
    overrides["PH2_IMGSZ"] = _cfg(event, "ph2_imgsz", "PH2_IMGSZ", 896)
    overrides["PH1_BATCH"] = _cfg(event, "ph1_batch", "PH1_BATCH", "-1")
    overrides["PH2_BATCH"] = _cfg(event, "ph2_batch", "PH2_BATCH", "-1")
    overrides["PH1_WORKERS"] = _cfg(
        event, "ph1_workers", "PH1_WORKERS", _cfg(event, "workers", "WORKERS", "4")
    )
    overrides["PH2_WORKERS"] = _cfg(
        event, "ph2_workers", "PH2_WORKERS", _cfg(event, "workers", "WORKERS", "4")
    )
    overrides["PH1_FREEZE"] = _cfg(event, "ph1_freeze", "PH1_FREEZE", "10")
    overrides["PH2_FREEZE"] = _cfg(event, "ph2_freeze", "PH2_FREEZE", "0")
    overrides["PH1_LR0"] = _cfg(event, "ph1_lr0", "PH1_LR0", "0.01")
    overrides["PH2_LR0"] = _cfg(event, "ph2_lr0", "PH2_LR0", "0.003")
    overrides["PH1_LRF"] = _cfg(event, "ph1_lrf", "PH1_LRF", "0.01")
    overrides["PH2_LRF"] = _cfg(event, "ph2_lrf", "PH2_LRF", "0.01")
    overrides["PH1_MOSAIC"] = _cfg(event, "ph1_mosaic", "PH1_MOSAIC", "0.7")
    overrides["PH2_MOSAIC"] = _cfg(event, "ph2_mosaic", "PH2_MOSAIC", "0.7")
    overrides["PH1_CLOSE_MOSAIC"] = _cfg(event, "ph1_close_mosaic", "PH1_CLOSE_MOSAIC", "10")
    overrides["PH2_CLOSE_MOSAIC"] = _cfg(event, "ph2_close_mosaic", "PH2_CLOSE_MOSAIC", "20")
    overrides["PH1_DEGREES"] = _cfg(event, "ph1_degrees", "PH1_DEGREES", "8")
    overrides["PH2_DEGREES"] = _cfg(event, "ph2_degrees", "PH2_DEGREES", "8")
    overrides["PH1_TRANSLATE"] = _cfg(event, "ph1_translate", "PH1_TRANSLATE", "0.08")
    overrides["PH2_TRANSLATE"] = _cfg(event, "ph2_translate", "PH2_TRANSLATE", "0.08")
    overrides["PH1_AUG_SCALE"] = _cfg(event, "ph1_aug_scale", "PH1_AUG_SCALE", "0.35")
    overrides["PH2_AUG_SCALE"] = _cfg(event, "ph2_aug_scale", "PH2_AUG_SCALE", "0.35")
    overrides["PH1_FLIPLR"] = _cfg(event, "ph1_fliplr", "PH1_FLIPLR", "0.5")
    overrides["PH2_FLIPLR"] = _cfg(event, "ph2_fliplr", "PH2_FLIPLR", "0.5")
    overrides["PH1_COPY_PASTE"] = _cfg(event, "ph1_copy_paste", "PH1_COPY_PASTE", "0.40")
    overrides["PH2_COPY_PASTE"] = _cfg(event, "ph2_copy_paste", "PH2_COPY_PASTE", "0.60")
    overrides["PH1_CLS"] = _cfg(event, "ph1_cls", "PH1_CLS", "1.0")
    overrides["PH2_CLS"] = _cfg(event, "ph2_cls", "PH2_CLS", "1.0")
    overrides["PH1_ERASING"] = _cfg(event, "ph1_erasing", "PH1_ERASING", "0.1")
    overrides["PH2_ERASING"] = _cfg(event, "ph2_erasing", "PH2_ERASING", "0.1")
    overrides["PH1_CLASS_WEIGHTS_AUTO"] = _cfg(
        event, "ph1_class_weights_auto", "PH1_CLASS_WEIGHTS_AUTO", "1"
    )
    overrides["PH2_CLASS_WEIGHTS_AUTO"] = _cfg(
        event, "ph2_class_weights_auto", "PH2_CLASS_WEIGHTS_AUTO", "1"
    )
    overrides["PH1_CLASS_WEIGHTS_POWER"] = _cfg(
        event, "ph1_class_weights_power", "PH1_CLASS_WEIGHTS_POWER", "0.5"
    )
    overrides["PH2_CLASS_WEIGHTS_POWER"] = _cfg(
        event, "ph2_class_weights_power", "PH2_CLASS_WEIGHTS_POWER", "0.7"
    )
    overrides["PH1_PER_CLASS_METRICS"] = _cfg(
        event, "ph1_per_class_metrics", "PH1_PER_CLASS_METRICS", "1"
    )
    overrides["PH2_PER_CLASS_METRICS"] = _cfg(
        event, "ph2_per_class_metrics", "PH2_PER_CLASS_METRICS", "1"
    )
    overrides["PH1_SAVE_PERIOD"] = _cfg(event, "ph1_save_period", "PH1_SAVE_PERIOD", "5")
    overrides["PH2_SAVE_PERIOD"] = _cfg(event, "ph2_save_period", "PH2_SAVE_PERIOD", "3")
    overrides["PH2_DROPOUT"] = _cfg(event, "ph2_dropout", "PH2_DROPOUT", "0.10")
    overrides["PH2_COS_LR"] = _cfg(event, "ph2_cos_lr", "PH2_COS_LR", "1")
    # fl_gamma removed from ultralytics >= 8.3.x — default to disabled to avoid
    # passing a flag that train_yolo.py now silently ignores anyway.
    overrides["PH2_FOCAL_LOSS"] = _cfg(event, "ph2_focal_loss", "PH2_FOCAL_LOSS", "0")
    overrides["PH2_FOCAL_GAMMA"] = _cfg(event, "ph2_focal_gamma", "PH2_FOCAL_GAMMA", "1.5")

    # Safety: YOLO crashes when close_mosaic >= epochs (it tries to disable mosaic
    # in the last N epochs but there aren't enough epochs to do so).
    # Force close_mosaic=0 in that case to disable the feature entirely.
    for phase, epochs_key, cm_key in [
        ("PH1", "PH1_EPOCHS", "PH1_CLOSE_MOSAIC"),
        ("PH2", "PH2_EPOCHS", "PH2_CLOSE_MOSAIC"),
    ]:
        try:
            if int(overrides[epochs_key]) <= int(overrides[cm_key]):
                logger.warning(
                    "%s_EPOCHS=%s <= %s=%s — forcing %s=0 to avoid YOLO crash",
                    phase,
                    overrides[epochs_key],
                    cm_key,
                    overrides[cm_key],
                    cm_key,
                )
                overrides[cm_key] = "0"
        except (ValueError, KeyError):
            pass

    env_prefix = " ".join(f"{k}={v}" for k, v in overrides.items())
    # Note: no separate CUDA pre-check here. Running a Python CUDA check as a
    # separate process before training initializes the CUDA context, then
    # destroys it on exit. On some Vast.ai hosts this leaves the driver in an
    # inconsistent state so the training process can't re-initialize CUDA.
    # CUDA failures are detected from the training log instead (see worker.py).
    train_cmd = f"cd /work && PYTHONPATH=/work {env_prefix} bash /work/run_service.sh"

    gcs_uri = _checkpoint_gcs_uri(event)
    if not gcs_uri:
        return train_cmd

    sync_interval = int(os.getenv("TRAIN_CHECKPOINT_SYNC_INTERVAL_SEC", "300"))
    # Restore checkpoints from GCS before training (non-fatal if none exist),
    # run a background uploader that syncs every N seconds while training,
    # do a final sync after training, then exit with training's exit code.
    # NOTE: Do NOT use `exit $_CVAPP_RC` here — _start_training_detached wraps
    # this string as: `bash -c "<cmd>; echo $? > /work/train.exit"`.
    # An `exit` inside <cmd> terminates bash before the echo runs, so train.exit
    # never gets written and _poll_training_status returns EXIT:unknown → code 1
    # even on successful training. Use a subshell `(exit $_CVAPP_RC)` instead,
    # which sets $? in the parent shell without terminating it.
    return (
        f"mkdir -p /work/checkpoints/ph1 /work/checkpoints/ph2"
        f" && gsutil -m rsync -r {gcs_uri}/ /work/checkpoints/ 2>/dev/null || true"
        f"; ( while true; do sleep {sync_interval};"
        f" gsutil -m rsync -r /work/checkpoints/ {gcs_uri}/ 2>/dev/null || true;"
        f" done ) & _CVAPP_CKPT_PID=$!"
        f"; {train_cmd}"
        f"; _CVAPP_RC=$?"
        f"; kill $_CVAPP_CKPT_PID 2>/dev/null || true"
        f"; gsutil -m rsync -r /work/checkpoints/ {gcs_uri}/ 2>/dev/null || true"
        f"; (exit $_CVAPP_RC)"
    )


def build_run_cmd(event: TrainingJobEvent) -> str:
    override = os.getenv("TRAIN_RUN_CMD")
    if override:
        return override

    if os.getenv("TRAIN_MODE", "two_phase") == "two_phase":
        return _build_two_phase_cmd(event)

    base = os.getenv("TRAIN_CMD_BASE", "yolo train")
    model = _cfg(event, "model", "TRAIN_MODEL", "yolo11s.pt")
    name = _cfg(event, "name", "TRAIN_NAME", event.job_id)
    project = _cfg(event, "project", "TRAIN_PROJECT", "runs")
    epochs = _cfg(event, "epochs", "TRAIN_EPOCHS", 1)
    device = _cfg(event, "device", "DEVICE", "0")
    patience = _cfg(event, "patience", "TRAIN_PATIENCE", 50)
    save = _cfg(event, "save", "TRAIN_SAVE", True)

    data = _cfg(event, "data", "TRAIN_DATA")
    args = []
    if data:
        args.append(f"data={data}")
    args.extend(
        [
            f"model={model}",
            f"name={name}",
            f"project={project}",
            f"epochs={epochs}",
            f"device={device}",
            f"patience={patience}",
            f"save={'true' if str(save).lower() in ('1', 'true', 'yes', 'on') else 'false'}",
        ]
    )
    return f"{base} {' '.join(args)}".strip()


def resolve_artifact_src(event: TrainingJobEvent) -> list[str]:
    """Return ordered candidate paths for the trained model artifact.

    The first path that exists on the remote instance will be downloaded.
    ``best.pt`` is preferred; ``last.pt`` is the fallback for runs that were
    too short to produce a best-checkpoint (e.g. test runs with very few
    epochs).
    """
    explicit = os.getenv("TRAIN_ARTIFACT_SRC")
    if explicit:
        return [explicit]

    if os.getenv("TRAIN_MODE", "two_phase") == "two_phase":
        runs_dir = str(_cfg(event, "runs_dir", "RUNS_DIR", "/work/runs")).rstrip("/")
        base_name = _cfg(event, "name", "TRAIN_NAME", event.job_id)
        ph2_name = _cfg(event, "ph2_name", "PH2_NAME", f"{base_name}_ph2")
        weights_dir = f"{runs_dir}/segment/{ph2_name}/weights"
        return [f"{weights_dir}/best.pt", f"{weights_dir}/last.pt"]

    runs_dir = os.getenv("TRAIN_RUNS_DIR", "/root/runs").rstrip("/")
    task_dir = os.getenv("TRAIN_TASK", "detect").strip("/")
    project = _cfg(event, "project", "TRAIN_PROJECT", "runs")
    name = _cfg(event, "name", "TRAIN_NAME", event.job_id)
    weights_dir = f"{runs_dir}/{task_dir}/{project}/{name}/weights"
    return [f"{weights_dir}/best.pt", f"{weights_dir}/last.pt"]
