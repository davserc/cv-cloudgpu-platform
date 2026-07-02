import base64
import json
import os
from typing import Any
from uuid import uuid4


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
        from google.cloud import storage
    except Exception as exc:
        raise RuntimeError("google-cloud-storage not available") from exc

    gcp_sa_b64 = os.getenv("GCP_SA_B64")
    if not gcp_sa_b64:
        return storage.Client()

    info = _decode_service_account(gcp_sa_b64)

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
        project = os.getenv("GCLOUD_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT", "na")
        return storage.Client(credentials=creds, project=project)

    return storage.Client.from_service_account_info(info)


def _upload_base_uri() -> str:
    return os.getenv(
        "INFER_UPLOAD_GCS_BASE_URI",
        "gs://unlu-genai-serranodavid-computer_vision_yolo/uploads",
    )


def upload_bytes_to_gcs(data: bytes, filename: str, content_type: str | None = None) -> str:
    client = _get_gcs_client()
    bucket_name, prefix = _parse_gs_uri(_upload_base_uri())
    blob_path = f"{prefix}/{uuid4()}_{filename}".strip("/")
    bucket = client.bucket(bucket_name)
    bucket.blob(blob_path).upload_from_string(data, content_type=content_type)
    return f"gs://{bucket_name}/{blob_path}"
