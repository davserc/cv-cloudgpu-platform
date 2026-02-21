FROM python:3.11-slim

ARG CLOUDGPU_GIT_TOKEN

WORKDIR /app

COPY libs/common /app/libs/common
COPY libs/contracts /app/libs/contracts
COPY services/training-service /app/services/training-service

RUN apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -e /app/libs/common \
    && pip install --no-cache-dir -e /app/libs/contracts \
    && pip install --no-cache-dir fastapi "uvicorn[standard]" kafka-python google-cloud-storage \
    && if [ -n "$CLOUDGPU_GIT_TOKEN" ]; then \
         pip install --no-cache-dir "git+https://${CLOUDGPU_GIT_TOKEN}@github.com/davserc/cloudgpu-automation-lib.git@main"; \
       else \
         pip install --no-cache-dir "git+https://github.com/davserc/cloudgpu-automation-lib.git@main"; \
       fi
RUN python - <<'PY'
from pathlib import Path
import subprocess

path = Path("/usr/local/lib/python3.11/site-packages/vast_service.py")
text = path.read_text()

if "def _push_gcp_json" not in text:
    insert = """
def _push_gcp_json(host, port, scp_bin="scp"):
    local = Path("/tmp/gcp.json")
    if not local.exists():
        print("vast_service: /tmp/gcp.json not found; skipping scp", flush=True)
        return
    scp_cmd = [
        scp_bin,
        "-P", str(port),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        str(local),
        f"root@{host}:/root/gcp.json",
    ]
    print(f"vast_service: scp /tmp/gcp.json -> root@{host}:{port}:/root/gcp.json", flush=True)
    try:
        subprocess.run(scp_cmd, check=True)
    except Exception as exc:
        print(f"vast_service: scp failed: {exc}", flush=True)
        raise
    print("vast_service: scp OK", flush=True)

"""
    text = text.replace("from pathlib import Path\n", "from pathlib import Path\n" + insert)

text = text.replace(
    "    ssh_cmd = [\n",
    "    _push_gcp_json(host, port)\n    ssh_cmd = [\n"
)

path.write_text(text)
PY

ENV PYTHONPATH=/app
WORKDIR /app/services/training-service

COPY services/training-service/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


