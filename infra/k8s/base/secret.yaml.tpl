# Template — copy to secret.yaml, fill in real values, then apply:
#   kubectl apply -f infra/k8s/base/secret.yaml
# DO NOT commit secret.yaml with real values (it is in .gitignore).
apiVersion: v1
kind: Secret
metadata:
  name: cv-platform-secrets
  namespace: cv-platform
type: Opaque
stringData:
  DB_USER: "CHANGE_ME"
  DB_PASSWORD: "CHANGE_ME"
  DATABASE_URL: "postgresql+psycopg2://CHANGE_ME:CHANGE_ME@postgres:5432/computer-vision"
  VAST_API_KEY: "CHANGE_ME"
  API_GATEWAY_API_KEY: "CHANGE_ME"
  # Base64-encoded ed25519 private key used by training-worker to SSH into Vast.ai instances.
  # Generate with: base64 -w0 secrets/vast_ed25519
  VAST_SSH_PRIVATE_KEY: "CHANGE_ME"
