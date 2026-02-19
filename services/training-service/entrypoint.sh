#!/usr/bin/env bash
set -euo pipefail

SSH_DIR="/root/.ssh"
KEY_SRC="${VAST_SSH_KEY_SRC:-$SSH_DIR/id_ed25519_src}"
KEY_DST="$SSH_DIR/id_ed25519"
KNOWN_SRC="${VAST_SSH_KNOWN_HOSTS_SRC:-$SSH_DIR/known_hosts_src}"
KNOWN_DST="$SSH_DIR/known_hosts"

mkdir -p "$SSH_DIR"

if [ -f "$KEY_SRC" ]; then
  cp -f "$KEY_SRC" "$KEY_DST" || true
fi
if [ -f "$KNOWN_SRC" ]; then
  cp -f "$KNOWN_SRC" "$KNOWN_DST" || true
fi

if [ -f "$KEY_DST" ]; then
  chmod 600 "$KEY_DST" || true
fi

exec "$@"
