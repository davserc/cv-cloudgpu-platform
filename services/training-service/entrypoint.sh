#!/usr/bin/env bash
set -euo pipefail

SSH_DIR="/root/.ssh"
KEY_DIR="${VAST_SSH_KEY_DIR:-/opt/app/secrets/vast_ssh}"
KEY_PATH="${VAST_SSH_KEY_PATH:-$KEY_DIR/id_ed25519}"
KEY_PUB_PATH="${KEY_PATH}.pub"
KEY_SRC="${VAST_SSH_KEY_SRC:-$KEY_PATH}"
KEY_DST="$SSH_DIR/id_ed25519"
KNOWN_SRC="${VAST_SSH_KNOWN_HOSTS_SRC:-$SSH_DIR/known_hosts_src}"
KNOWN_DST="$SSH_DIR/known_hosts"

mkdir -p "$SSH_DIR"

if [ "${VAST_AUTO_SSH_KEY:-0}" = "1" ]; then
  mkdir -p "$(dirname "$KEY_PATH")"
  if [ ! -f "$KEY_PATH" ]; then
    echo "Generating SSH key at $KEY_PATH"
    ssh-keygen -t ed25519 -f "$KEY_PATH" -N "" -C "vast-gpu"
  fi
fi

if [ "${VAST_AUTO_REGISTER_SSH_KEY:-0}" = "1" ]; then
  if [ -f "$KEY_PUB_PATH" ] && [ -n "${VAST_API_KEY:-}" ]; then
    python - <<'PY'
import os
import sys

try:
    from vast_gpu_manager import VastGPUManager
except Exception as exc:
    print(f"WARNING: failed to import vast_gpu_manager ({exc}); skipping SSH key registration", file=sys.stderr)
    raise SystemExit(0)

api_key = os.environ.get("VAST_API_KEY")
key_path = os.environ.get("VAST_SSH_KEY_PATH") or os.environ.get("VAST_SSH_KEY_DIR", "/opt/app/secrets/vast_ssh") + "/id_ed25519"
pub_path = f"{key_path}.pub"

try:
    key = open(pub_path, "r", encoding="utf-8").read()
except Exception as exc:
    raise SystemExit(f"Failed to read public key at {pub_path}: {exc}")

manager = VastGPUManager(api_key=api_key)
manager.add_ssh_key(key)
print("Registered SSH public key with Vast")
PY
  fi
fi

if [ -f "$KEY_SRC" ]; then
  cp -f "$KEY_SRC" "$KEY_DST" || true
fi
if [ -f "$KNOWN_SRC" ]; then
  cp -f "$KNOWN_SRC" "$KNOWN_DST" || true
fi

if [ -f "$KEY_DST" ]; then
  chmod 600 "$KEY_DST" || true
fi

if [ -f "$KEY_DST" ]; then
  cat > "$SSH_DIR/config" <<'EOF'
Host *
  IdentityFile /root/.ssh/id_ed25519
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
  UserKnownHostsFile /root/.ssh/known_hosts
EOF
  chmod 600 "$SSH_DIR/config" || true
fi

exec "$@"
