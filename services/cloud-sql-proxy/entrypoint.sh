#!/bin/sh
set -eu

SECRETS_DIR="/secrets"
CREDS_PATH="${SECRETS_DIR}/cloudsql.json"

mkdir -p "${SECRETS_DIR}"

if [ -n "${GCP_SA_B64:-}" ]; then
  echo "${GCP_SA_B64}" | tr -d '\r' | base64 -d > "${CREDS_PATH}"
  chmod 600 "${CREDS_PATH}"
fi

if [ ! -s "${CREDS_PATH}" ]; then
  echo "cloud-sql-proxy: missing credentials at ${CREDS_PATH}" >&2
  exit 1
fi

if [ -z "${CLOUD_SQL_INSTANCE:-}" ]; then
  echo "cloud-sql-proxy: CLOUD_SQL_INSTANCE is required" >&2
  exit 1
fi

exec /cloud-sql-proxy \
  --address=0.0.0.0 \
  --port=5432 \
  --credentials-file="${CREDS_PATH}" \
  "${CLOUD_SQL_INSTANCE}"
