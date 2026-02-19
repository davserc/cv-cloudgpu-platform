import os
from pathlib import Path

from contracts.events import TrainingJobEvent


def model_base_name(model: str) -> str:
    name = Path(model).name
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name


def build_run_cmd(event: TrainingJobEvent) -> str:
    override = os.getenv("TRAIN_RUN_CMD")
    if override:
        return override

    base = os.getenv("TRAIN_CMD_BASE", "yolo train")
    data = None
    if event.config and isinstance(event.config, dict):
        data = event.config.get("data")
    if not data:
        data = os.getenv("TRAIN_DATA")

    args = []
    if data:
        args.append(f"data={data}")
    args.extend(
        [
            f"model={event.model}",
            f"name={event.name}",
            f"project={event.project}",
            f"epochs={event.epochs}",
            f"imgsz={event.imgsz}",
            f"batch={event.batch}",
            f"device={event.device}",
            f"patience={event.patience}",
            f"save={'true' if event.save else 'false'}",
        ]
    )
    return f"{base} {' '.join(args)}".strip()
