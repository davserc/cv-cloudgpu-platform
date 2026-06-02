apiVersion: v1
kind: Secret
metadata:
  name: cv-platform-secrets
  namespace: cv-platform
type: Opaque
stringData:
  DB_USER: "app"
  DB_PASSWORD: "CHANGE_ME_DB_PASSWORD"
  # Local: apunta al pod postgres dentro del cluster kind
  DATABASE_URL: "postgresql+psycopg2://app:CHANGE_ME_DB_PASSWORD@postgres:5432/computer-vision"
  VAST_API_KEY: "CHANGE_ME_VAST_API_KEY"
  API_GATEWAY_API_KEY: "CHANGE_ME_API_KEY"
  GRAFANA_ADMIN_PASSWORD: "CHANGE_ME_GRAFANA_PASSWORD"
  GCP_SA_B64: "CHANGE_ME_GCP_SA_B64"
  DOCKERHUB_USERNAME: "CHANGE_ME_DOCKERHUB_USERNAME"
  DOCKERHUB_PASSWORD: "CHANGE_ME_DOCKERHUB_PASSWORD"
  NOTIFY_SMTP_PASSWORD: "CHANGE_ME_SMTP_PASSWORD"
data:
  # base64 de la clave SSH privada ed25519 para vast.ai
  # Linux:   base64 -w0 ~/.ssh/id_ed25519_vast
  # Windows: [Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\Users\<user>\.ssh\id_ed25519_vast"))
  VAST_SSH_PRIVATE_KEY: "CHANGE_ME_BASE64_SSH_KEY"
