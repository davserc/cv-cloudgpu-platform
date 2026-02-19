import base64
import json
from pathlib import Path
from typing import Any


def parse_gs_uri(uri: str) -> tuple[str, str]:
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

    # Try base64 first (expected).
    try:
        compact = "".join(raw.split())
        decoded = base64.b64decode(compact).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        pass

    # Fallback: allow raw JSON.
    try:
        return json.loads(raw)
    except Exception as exc:
        raise RuntimeError("Failed to decode GCP_SA_B64") from exc


def get_gcs_client(gcp_sa_b64: str | None):
    try:
        from google.cloud import storage  # type: ignore
    except Exception as exc:
        raise RuntimeError("google-cloud-storage not available in environment") from exc

    if not gcp_sa_b64:
        return storage.Client()

    info = _decode_service_account(gcp_sa_b64)

    return storage.Client.from_service_account_info(info)


def upload_artifact_to_gcs(
    *,
    artifact_path: Path,
    base_uri: str,
    model_base: str,
    job_id: str,
    metadata: dict[str, Any],
    gcp_sa_b64: str | None,
) -> tuple[str, str]:
    client = get_gcs_client(gcp_sa_b64)
    bucket_name, base_prefix = parse_gs_uri(base_uri)
    prefix = f"{base_prefix}/{model_base}/model-{job_id}".strip("/")
    artifact_blob_path = f"{prefix}/best.pt"
    metadata_blob_path = f"{prefix}/metadata.json"

    artifact_uri = f"gs://{bucket_name}/{artifact_blob_path}"
    metadata_uri = f"gs://{bucket_name}/{metadata_blob_path}"
    metadata_out = dict(metadata)
    metadata_out["artifact_uri"] = artifact_uri
    metadata_out["metadata_uri"] = metadata_uri

    bucket = client.bucket(bucket_name)
    bucket.blob(artifact_blob_path).upload_from_filename(str(artifact_path))
    bucket.blob(metadata_blob_path).upload_from_string(
        json.dumps(metadata_out),
        content_type="application/json",
    )
    return artifact_uri, metadata_uri
