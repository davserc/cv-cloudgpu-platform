import base64
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_gs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI: {uri}")
    path = uri[len("gs://") :]
    if "/" not in path:
        return path, ""
    bucket, prefix = path.split("/", 1)
    return bucket, prefix.strip("/")


def _decode_service_account(value: str) -> dict[str, Any]:
    raw = value.strip()
    if not raw:
        raise RuntimeError("GCP_SA_B64 is empty")

    try:
        compact = "".join(raw.split())
        decoded = base64.b64decode(compact).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        pass

    try:
        return json.loads(raw)
    except Exception as exc:
        raise RuntimeError("Failed to decode GCP_SA_B64") from exc


def _get_gcs_client():
    try:
        from google.cloud import storage  # type: ignore
    except Exception as exc:
        raise RuntimeError("google-cloud-storage not available") from exc

    gcp_sa_b64 = os.getenv("GCP_SA_B64")
    if not gcp_sa_b64:
        return storage.Client()

    info = _decode_service_account(gcp_sa_b64)

    # authorized_user credentials (gcloud auth login) requieren un flujo diferente
    # al de una service account — mismo patrón que training-service/app/gcs_utils.py.
    if info.get("type") == "authorized_user":
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=None,
            refresh_token=info["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=info["client_id"],
            client_secret=info["client_secret"],
        )
        creds.refresh(Request())
        # storage.Client sin project explícito llama a google.auth.default() para
        # detectarlo, lo cual falla sin ADC configurado en el pod. Cualquier project
        # no-None evita esa detección; no hace falta uno válido para buckets existentes.
        project = os.getenv("GCLOUD_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT", "na")
        return storage.Client(credentials=creds, project=project)

    return storage.Client.from_service_account_info(info)


def _download_http(uri: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(uri, timeout=60) as resp, dst.open("wb") as fh:
        fh.write(resp.read())


def _download_gcs(uri: str, dst: Path) -> None:
    client = _get_gcs_client()
    bucket_name, blob_path = _parse_gs_uri(uri)
    dst.parent.mkdir(parents=True, exist_ok=True)
    bucket = client.bucket(bucket_name)
    bucket.blob(blob_path).download_to_filename(str(dst))


def download_artifact_to_cache(uri: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    name = Path(uri).name
    if name == "":
        name = "model.pt"
    dst = cache_dir / name
    if dst.exists():
        return dst
    if uri.startswith("gs://"):
        _download_gcs(uri, dst)
    elif uri.startswith("http://") or uri.startswith("https://"):
        _download_http(uri, dst)
    else:
        # local path
        return Path(uri)
    return dst


def _registry_url() -> str | None:
    return os.getenv("MODEL_REGISTRY_URL")


def get_model_entry(model_id: str) -> dict[str, Any] | None:
    base = _registry_url()
    if not base:
        return None
    url = f"{base.rstrip('/')}/{model_id}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def list_models() -> list[dict[str, Any]]:
    base = _registry_url()
    if not base:
        return []
    try:
        with urllib.request.urlopen(base, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("items", [])
    except Exception:
        return []


def pick_default_model() -> dict[str, Any] | None:
    items = list_models()
    if not items:
        return None
    active = [m for m in items if m.get("status") == "active"]
    candidates = active or items

    def _parse_dt(val: str | None) -> float:
        if not val:
            return 0.0
        try:
            return datetime.fromisoformat(val).timestamp()
        except Exception:
            return 0.0

    candidates.sort(
        key=lambda m: _parse_dt(m.get("updated_at") or m.get("created_at")), reverse=True
    )
    return candidates[0]
