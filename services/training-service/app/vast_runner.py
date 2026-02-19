import logging
import os
from pathlib import Path
import base64

logger = logging.getLogger(__name__)


def get_vast_helpers():
    try:
        from vast_service import train_with_cheapest_instance
    except Exception as exc:
        raise RuntimeError(
            "vast_service not available. Install cloudgpu-automation-lib in the environment."
        ) from exc
    return {"train_with_cheapest_instance": train_with_cheapest_instance}

def _ensure_gcp_json(gcp_sa_b64: str | None) -> None:
    if not gcp_sa_b64:
        return
    try:
        decoded = base64.b64decode(gcp_sa_b64, validate=True)
    except Exception as exc:
        logger.warning("Invalid GCP_SA_B64; skipping /root/gcp.json write (%s)", exc)
        return
    path = Path("/tmp/gcp.json")
    path.write_bytes(decoded)
    os.chmod(path, 0o600)

def train_on_instance(
    *,
    api_key: str | None,
    image: str,
    ports: str | None,
    dataset_dst: str,
    run_cmd: str,
    artifact_src: str,
    artifact_dst: Path,
    log_path: str | None,
    max_price: float | None,
    min_cuda: float | None,
    max_cuda: float | None,
    gcp_sa_b64: str | None,
    dataset_gs_uri: str | None,
    dataset_archive_name: str | None,
    extract_cmd: str | None,
    install_gsutil: bool,
    train_dataset_url: str | None,
    ssh_timeout_sec: int,
    ssh_poll_interval_sec: int,
    cmd_retries: int,
    cmd_backoff_sec: float,
) -> None:
    helpers = get_vast_helpers()
    max_launch_attempts = int(os.getenv("VAST_MAX_LAUNCH_ATTEMPTS", "5"))
    destroy_retries = int(os.getenv("VAST_DESTROY_RETRIES", "3"))
    destroy_backoff_sec = float(os.getenv("VAST_DESTROY_BACKOFF_SEC", "5"))
    launch_retry_backoff_sec = float(os.getenv("VAST_LAUNCH_RETRY_BACKOFF_SEC", "5"))
    offer_blacklist_path = os.getenv("VAST_OFFER_BLACKLIST_PATH", ".vast_offer_blacklist.json")
    offer_blacklist_ttl_sec = int(os.getenv("VAST_OFFER_BLACKLIST_TTL_SEC", "3600"))

    _ensure_gcp_json(gcp_sa_b64)

    kwargs = {
        "api_key": api_key,
        "job_id": os.getenv("JOB_ID"),
        "image": image,
        "ports": ports,
        "dataset_dst": dataset_dst,
        "run_cmd": run_cmd,
        "artifact_src": artifact_src,
        "artifact_dst": artifact_dst,
        "log_path": log_path,
        "gcp_sa_b64": gcp_sa_b64,
        "dataset_gs_uri": dataset_gs_uri,
        "dataset_archive_name": dataset_archive_name,
        "extract_cmd": extract_cmd,
        "install_gsutil": install_gsutil,
        "train_dataset_url": train_dataset_url,
        "ssh_timeout_sec": ssh_timeout_sec,
        "ssh_poll_interval_sec": ssh_poll_interval_sec,
        "cmd_retries": cmd_retries,
        "cmd_backoff_sec": cmd_backoff_sec,
        "max_price": max_price,
        "min_cuda": min_cuda,
        "max_cuda": max_cuda,
        "max_launch_attempts": max_launch_attempts,
        "launch_retry_backoff_sec": launch_retry_backoff_sec,
        "destroy_retries": destroy_retries,
        "destroy_backoff_sec": destroy_backoff_sec,
        "offer_blacklist_path": offer_blacklist_path,
        "offer_blacklist_ttl_sec": offer_blacklist_ttl_sec,
    }
    try:
        import inspect

        params = set(inspect.signature(helpers["train_with_cheapest_instance"]).parameters.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in params}
    except Exception:
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

    helpers["train_with_cheapest_instance"](**filtered_kwargs)
