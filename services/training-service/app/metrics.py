import re
from pathlib import Path


def parse_ultralytics_metrics(log_path: str | None) -> dict[str, float]:
    if not log_path:
        return {}
    try:
        text = Path(log_path).read_text(errors="ignore")
    except OSError:
        return {}

    text = text.replace("\r", "\n")
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)

    pattern = re.compile(
        r"^\s*all\s+\d+\s+\d+\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*$",
        re.MULTILINE,
    )
    matches = pattern.findall(text)
    if not matches:
        return {}

    box_p, box_r, map50, map50_95 = matches[-1]
    return {
        "box_p": float(box_p),
        "box_r": float(box_r),
        "mAP50": float(map50),
        "mAP50_95": float(map50_95),
        "mAP": float(map50_95),
    }
