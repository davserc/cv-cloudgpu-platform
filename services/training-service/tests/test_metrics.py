import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.metrics import parse_ultralytics_metrics

SAMPLE_LOG = """\
                 Class     Images  Instances      Box(P          R      mAP50  mAP50-95):
                   all        100       1000      0.752      0.631      0.698      0.432
"""

ANSI_LOG = "\x1b[1mall        100       1000      0.800      0.700      0.750      0.500\x1b[0m"


def test_parse_returns_empty_for_none():
    assert parse_ultralytics_metrics(None) == {}


def test_parse_returns_empty_for_missing_file():
    assert parse_ultralytics_metrics("/nonexistent/path.log") == {}


def test_parse_extracts_metrics(tmp_path):
    log_file = tmp_path / "train.log"
    log_file.write_text(SAMPLE_LOG)
    metrics = parse_ultralytics_metrics(str(log_file))
    assert metrics["box_p"] == pytest.approx(0.752)
    assert metrics["box_r"] == pytest.approx(0.631)
    assert metrics["mAP50"] == pytest.approx(0.698)
    assert metrics["mAP50_95"] == pytest.approx(0.432)
    assert metrics["mAP"] == pytest.approx(0.432)


def test_parse_strips_ansi_codes(tmp_path):
    log_file = tmp_path / "train.log"
    log_file.write_text(ANSI_LOG)
    metrics = parse_ultralytics_metrics(str(log_file))
    assert metrics.get("mAP50") == pytest.approx(0.750)


def test_parse_returns_last_match(tmp_path):
    multi_log = (
        "     all   100  1000  0.600  0.500  0.550  0.300\n"
        "     all   100  1000  0.800  0.700  0.750  0.500\n"
    )
    log_file = tmp_path / "train.log"
    log_file.write_text(multi_log)
    metrics = parse_ultralytics_metrics(str(log_file))
    assert metrics["mAP50"] == pytest.approx(0.750)


def test_parse_returns_empty_when_no_match(tmp_path):
    log_file = tmp_path / "train.log"
    log_file.write_text("no metrics here\n")
    assert parse_ultralytics_metrics(str(log_file)) == {}
