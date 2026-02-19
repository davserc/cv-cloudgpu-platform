import json
import os
import sys
from urllib import error, request


def main() -> int:
    url = os.getenv("GATEWAY_URL", "http://localhost:8000/api/v1/train/")

    payload = {
        "batch": 8,
        "device": "0",
        "epochs": 1,
        "imgsz": 640,
        "model": "yolo11s.pt",
        "name": "exp_1",
        "patience": 50,
        "project": "runs",
        "save": True,
        "config": {
        "dataset_gs_uri": "gs://unlu-genai-serranodavid-computer_vision_yolo/taco.tar.gz",
          "install_gsutil": True
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            print(body)
            return 0
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        status_line = f"{exc.code} {exc.reason}".strip()
        if body:
            print(f"error: HTTP {status_line} - {body}")
        else:
            print(f"error: HTTP {status_line}")
        return 1
    except Exception as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
