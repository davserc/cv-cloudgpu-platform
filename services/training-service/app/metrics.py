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

    # Segmentation: all  N  N  box_P  box_R  box_mAP50  box_mAP50-95  mask_P  mask_R  mask_mAP50  mask_mAP50-95
    seg_pattern = re.compile(
        r"^\s*all\s+\d+\s+\d+\s+"
        r"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+"
        r"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*$",
        re.MULTILINE,
    )
    matches = seg_pattern.findall(text)
    if matches:
        bp, br, bm50, bm95, mp, mr, mm50, mm95 = matches[-1]
        return {
            "box_p": float(bp),
            "box_r": float(br),
            "box_mAP50": float(bm50),
            "box_mAP50_95": float(bm95),
            "mask_p": float(mp),
            "mask_r": float(mr),
            "mask_mAP50": float(mm50),
            "mask_mAP50_95": float(mm95),
            "mAP50": float(mm50),
            "mAP": float(mm95),
        }

    # Detection fallback: all  N  N  P  R  mAP50  mAP50-95
    det_pattern = re.compile(
        r"^\s*all\s+\d+\s+\d+\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*$",
        re.MULTILINE,
    )
    matches = det_pattern.findall(text)
    if matches:
        box_p, box_r, map50, map50_95 = matches[-1]
        return {
            "box_p": float(box_p),
            "box_r": float(box_r),
            "mAP50": float(map50),
            "mAP50_95": float(map50_95),
            "mAP": float(map50_95),
        }

    return {}
