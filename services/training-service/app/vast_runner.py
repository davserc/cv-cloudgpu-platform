import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def get_vast_helpers():
    try:
        import vast_service as _vast_service
        from vast_service import train_with_cheapest_instance
    except Exception as exc:
        raise RuntimeError(
            "vast_service not available. Install cloudgpu-automation-lib in the environment."
        ) from exc
    _maybe_patch_vast_service(_vast_service)
    return {"train_with_cheapest_instance": train_with_cheapest_instance}


def _maybe_patch_vast_service(vast_service_module) -> None:
    if getattr(vast_service_module, "_cvapp_patched", False):
        return

    def _inject_mkdir_for_df(cmd: object) -> object:
        if not isinstance(cmd, str):
            return cmd
        if "df " not in cmd:
            return cmd
        if "/work/datasets" not in cmd:
            return cmd
        if "mkdir -p /work/datasets" in cmd:
            return cmd
        return f"mkdir -p /work/datasets && {cmd}"

    vast_service_module._cvapp_last_run_failed = False
    # Patch run_capture to log full stdout/stderr for debugging.
    if hasattr(vast_service_module, "run_capture"):
        _orig_run_capture = vast_service_module.run_capture

        def _inject_disk_check(cmd: object) -> object:
            if not isinstance(cmd, str):
                return cmd
            if "gsutil -m cp " not in cmd:
                return cmd
            if "cvapp_disk_check:" in cmd:
                return cmd
            import re

            match = re.search(r"gsutil -m cp\s+(\S+)", cmd)
            dataset_uri = match.group(1) if match else ""
            if not dataset_uri:
                return cmd
            check_snippet = (
                "echo 'cvapp_disk_check: checking free space in /work/datasets' && "
                "df -h /work/datasets && "
                "AVAIL_BYTES=$(df -P -B1 --output=avail /work/datasets | tail -1 | tr -d ' ') && "
                f"NEED_BYTES=$(gsutil ls -l {dataset_uri} | awk 'NR==1 {{print $1}}') && "
                'if [ -z "$NEED_BYTES" ] || [ "$NEED_BYTES" = "0" ]; then '
                f"echo 'ERROR: cannot determine dataset size for {dataset_uri}' >&2; exit 42; fi && "
                'if [ "$AVAIL_BYTES" -lt "$NEED_BYTES" ]; then '
                "echo 'ERROR: insufficient disk space in /work/datasets. "
                "Need at least '$NEED_BYTES' bytes free before download.' >&2; exit 42; fi && "
            )
            return cmd.replace("gsutil -m cp", f"{check_snippet}gsutil -m cp", 1)

        def _run_capture_with_logs(*args, **kwargs):
            if "cmd" in kwargs:
                kwargs["cmd"] = _inject_disk_check(kwargs["cmd"])
            elif len(args) >= 3:
                args = list(args)
                args[2] = _inject_disk_check(args[2])
                args = tuple(args)
            res = _orig_run_capture(*args, **kwargs)
            try:
                rc = getattr(res, "returncode", None)
                stdout = getattr(res, "stdout", None)
                stderr = getattr(res, "stderr", None)
                if isinstance(res, tuple) and len(res) >= 3:
                    rc, stdout, stderr = res[0], res[1], res[2]
                if isinstance(stdout, bytes):
                    stdout = stdout.decode(errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode(errors="replace")
                if rc is not None and rc != 0:
                    vast_service_module._cvapp_last_run_failed = True
                if stdout:
                    logger.info("vast_service.run_capture stdout:\n%s", stdout)
                if stderr:
                    logger.warning("vast_service.run_capture stderr:\n%s", stderr)
                if rc is not None:
                    logger.info("vast_service.run_capture returncode=%s", rc)
            except Exception as exc:
                logger.warning("Failed to log run_capture output: %s", exc)
            return res

        vast_service_module.run_capture = _run_capture_with_logs

    # Patch run_output to create /work/datasets before disk checks.
    if hasattr(vast_service_module, "run_output"):
        _orig_run_output = vast_service_module.run_output

        def _run_output_with_mkdir(*args, **kwargs):
            if "cmd" in kwargs:
                kwargs["cmd"] = _inject_mkdir_for_df(kwargs["cmd"])
            elif len(args) >= 3:
                args = list(args)
                args[2] = _inject_mkdir_for_df(args[2])
                args = tuple(args)
            return _orig_run_output(*args, **kwargs)

        vast_service_module.run_output = _run_output_with_mkdir

    # Patch dataset onstart to always create /root/gcp.json even if apt-get fails.
    try:
        import services.vast.service.dataset as _vast_dataset

        if hasattr(_vast_dataset, "_build_onstart_cmd"):
            _orig_build_onstart_cmd = _vast_dataset._build_onstart_cmd

            def _build_onstart_cmd_safe(gcp_sa_b64, install_gsutil):
                # Inyectar la clave SSH del worker en authorized_keys para garantizar acceso
                # independientemente del mecanismo de key management de VAST.ai.
                ssh_pubkey = os.getenv("VAST_SSH_PUBLIC_KEY", "")
                parts = []
                if ssh_pubkey:
                    parts.append("mkdir -p /root/.ssh")
                    parts.append(f"echo {ssh_pubkey!r} >> /root/.ssh/authorized_keys")
                    parts.append("chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys")

                if not gcp_sa_b64:
                    return None, " ; ".join(parts) if parts else None
                env_vars = {"GCP_SA_B64": gcp_sa_b64}
                if install_gsutil:
                    parts.append("apt-get update && apt-get install -y google-cloud-cli || true")
                parts.append("printf %s \"$GCP_SA_B64\" | tr -d '\\r' | base64 -d > /root/gcp.json")
                parts.append("chmod 600 /root/gcp.json")
                return env_vars, " ; ".join(parts)

            _vast_dataset._build_onstart_cmd = _build_onstart_cmd_safe
    except Exception as exc:
        logger.warning("Failed to patch services.vast.service.dataset._build_onstart_cmd: %s", exc)

    # Patch services.vast.service.ssh.run_output (used by newer cloudgpu-automation-lib).
    try:
        import subprocess

        import services.vast.service.ssh as _vast_ssh

        def _inject_auth_debug(cmd: object) -> object:
            if not isinstance(cmd, str):
                return cmd
            if os.environ.get("DEBUG_GCLOUD_AUTH") != "1":
                return cmd
            return cmd.replace(
                "gcloud auth activate-service-account --key-file /root/gcp.json 2>/dev/null || true",
                "gcloud auth activate-service-account --key-file /root/gcp.json",
            )

        def _inject_gcp_json_probe(cmd: object) -> object:
            if not isinstance(cmd, str):
                return cmd
            if os.environ.get("DEBUG_GCP_JSON") != "1":
                return cmd
            if "gsutil -m cp " not in cmd:
                return cmd
            if "cvapp_gcp_json_check:" in cmd:
                return cmd
            probe = (
                "echo 'cvapp_gcp_json_check: /root/gcp.json' && "
                "echo 'cvapp_gcp_json_check: GCP_SA_B64 len='${#GCP_SA_B64} && "
                "ls -l /root/gcp.json || true && "
                "test -s /root/gcp.json && echo 'cvapp_gcp_json_check: present' || "
                "echo 'cvapp_gcp_json_check: missing' && "
            )
            return f"{probe}{cmd}"

        if hasattr(_vast_ssh, "run_output"):
            _ssh_run_output = _vast_ssh.run_output

            def _ssh_run_output_with_mkdir(*args, **kwargs):
                if "cmd" in kwargs:
                    kwargs["cmd"] = _inject_auth_debug(
                        _inject_gcp_json_probe(_inject_mkdir_for_df(kwargs["cmd"]))
                    )
                elif len(args) >= 3:
                    args = list(args)
                    args[2] = _inject_auth_debug(
                        _inject_gcp_json_probe(_inject_mkdir_for_df(args[2]))
                    )
                    args = tuple(args)
                return _ssh_run_output(*args, **kwargs)

            _vast_ssh.run_output = _ssh_run_output_with_mkdir

        if hasattr(_vast_ssh, "run_and_get_output"):
            _ssh_run_and_get_output = _vast_ssh.run_and_get_output

            def _ssh_run_and_get_output_with_mkdir(*args, **kwargs):
                if "cmd" in kwargs:
                    kwargs["cmd"] = _inject_auth_debug(
                        _inject_gcp_json_probe(_inject_mkdir_for_df(kwargs["cmd"]))
                    )
                elif len(args) >= 3:
                    args = list(args)
                    args[2] = _inject_auth_debug(
                        _inject_gcp_json_probe(_inject_mkdir_for_df(args[2]))
                    )
                    args = tuple(args)
                return _ssh_run_and_get_output(*args, **kwargs)

            _vast_ssh.run_and_get_output = _ssh_run_and_get_output_with_mkdir

        if hasattr(_vast_ssh, "run"):
            _ssh_run = _vast_ssh.run

            def _ssh_run_with_auth_debug(*args, **kwargs):
                if "cmd" in kwargs:
                    kwargs["cmd"] = _inject_auth_debug(_inject_gcp_json_probe(kwargs["cmd"]))
                elif len(args) >= 3:
                    args = list(args)
                    args[2] = _inject_auth_debug(_inject_gcp_json_probe(args[2]))
                    args = tuple(args)
                return _ssh_run(*args, **kwargs)

            _vast_ssh.run = _ssh_run_with_auth_debug

        if hasattr(_vast_ssh, "wait_for_ssh"):
            _wait_for_ssh = _vast_ssh.wait_for_ssh

            def _ssh_run_with_logs(
                manager,
                instance_id,
                cmd,
                ssh_bin="ssh",
                job_id=None,
            ):
                host, port = _wait_for_ssh(manager, instance_id, job_id=job_id)
                ssh_cmd = [
                    ssh_bin,
                    "-p",
                    str(port),
                    "-o",
                    "StrictHostKeyChecking=yes",
                    "-o",
                    f"UserKnownHostsFile={os.getenv('VAST_SSH_KNOWN_HOSTS_FILE', '/root/.ssh/known_hosts')}",
                    f"{os.getenv('VAST_SSH_USER', 'vast')}@{host}",
                    _inject_auth_debug(_inject_gcp_json_probe(cmd)),
                ]
                logger.info(
                    "run instance_id=%s job_id=%s host=%s port=%s cmd=%s",
                    instance_id,
                    job_id,
                    host,
                    port,
                    _inject_auth_debug(_inject_gcp_json_probe(cmd)),
                )
                completed = subprocess.run(ssh_cmd, capture_output=True, text=True)
                if completed.stdout:
                    logger.info("run stdout:\n%s", completed.stdout)
                if completed.stderr:
                    logger.warning("run stderr:\n%s", completed.stderr)
                if completed.returncode != 0:
                    raise subprocess.CalledProcessError(
                        completed.returncode, ssh_cmd, completed.stdout, completed.stderr
                    )
                return completed.returncode

            _vast_ssh.run = _ssh_run_with_logs
    except Exception as exc:
        logger.warning("Failed to patch services.vast.service.ssh.run_output: %s", exc)

    # Patch destroy_instance to optionally keep instance for debugging.
    if hasattr(vast_service_module, "destroy_instance"):
        _orig_destroy_instance = vast_service_module.destroy_instance

        def _destroy_instance_with_debug(*args, **kwargs):
            if os.getenv("VAST_KEEP_INSTANCE_ON_FAILURE") == "1" and getattr(
                vast_service_module, "_cvapp_last_run_failed", False
            ):
                logger.warning(
                    "VAST_KEEP_INSTANCE_ON_FAILURE=1 and last run failed: skipping destroy_instance"
                )
                return None
            delay = int(os.getenv("VAST_DESTROY_DELAY_SEC", "0") or "0")
            if delay > 0:
                logger.warning("VAST_DESTROY_DELAY_SEC=%s: sleeping before destroy_instance", delay)
                import time

                time.sleep(delay)
            return _orig_destroy_instance(*args, **kwargs)

        vast_service_module.destroy_instance = _destroy_instance_with_debug

    vast_service_module._cvapp_patched = True


def train_on_instance(
    *,
    api_key: str | None,
    image: str,
    ports: str | None,
    dataset_dst: str,
    run_cmd: str,
    artifact_src: str | list[str],
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

    try:
        import vast_service as _vast_service

        if hasattr(_vast_service, "_cvapp_last_run_failed"):
            _vast_service._cvapp_last_run_failed = False
    except Exception:
        pass

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
    kwargs["install_gsutil"] = True
    try:
        import inspect

        params = set(inspect.signature(helpers["train_with_cheapest_instance"]).parameters.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in params}
    except Exception:
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

    try:
        helpers["train_with_cheapest_instance"](**filtered_kwargs)
    except Exception as exc:
        logger.error("train_with_cheapest_instance failed: %s", exc, exc_info=True)
        raise
