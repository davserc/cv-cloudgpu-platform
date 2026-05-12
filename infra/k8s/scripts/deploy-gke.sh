#!/usr/bin/env bash
# Deploy cv-cloudgpu-platform en GKE (Google Kubernetes Engine).
# Prerequisites: gcloud CLI autenticado, kubectl, proyecto GCP creado.
#
# Uso:
#   export GCP_PROJECT=project-38c56a6f-24a9-45fb-aef
#   export GCP_REGION=us-central1   # opcional, default us-central1
#   bash infra/k8s/scripts/deploy-gke.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$SCRIPT_DIR/.."
SECRET_FILE="$K8S_DIR/base/secret.yaml"
CLUSTER="cv-platform"
GCP_REGION="${GCP_REGION:-us-central1}"

# ── Checks ────────────────────────────────────────────────────────────────────
command -v gcloud  >/dev/null || { echo "ERROR: gcloud no encontrado.  https://cloud.google.com/sdk"; exit 1; }
command -v kubectl >/dev/null || { echo "ERROR: kubectl no encontrado."; exit 1; }
: "${GCP_PROJECT:?Seteá GCP_PROJECT antes de ejecutar.  export GCP_PROJECT=<tu-proyecto>}"

if [[ ! -f "$SECRET_FILE" ]]; then
  echo "ERROR: $SECRET_FILE no existe."
  echo "  cp infra/k8s/base/secret.yaml.tpl infra/k8s/base/secret.yaml"
  echo "  # completá los valores reales en secret.yaml"
  exit 1
fi

# ── Autenticación GCP ─────────────────────────────────────────────────────────
echo "→ Verificando autenticación GCP..."
gcloud config set project "$GCP_PROJECT"

# ── Cluster GKE ───────────────────────────────────────────────────────────────
if gcloud container clusters describe "$CLUSTER" \
     --region="$GCP_REGION" --project="$GCP_PROJECT" &>/dev/null; then
  echo "✓ Cluster GKE '$CLUSTER' ya existe."
else
  echo "→ Creando cluster GKE '$CLUSTER' (tarda ~3 min)..."
  gcloud container clusters create "$CLUSTER" \
    --project="$GCP_PROJECT" \
    --region="$GCP_REGION" \
    --num-nodes=2 \
    --machine-type=e2-standard-2 \
    --disk-size=50GB \
    --enable-autoupgrade \
    --workload-pool="${GCP_PROJECT}.svc.id.goog"
fi

# Obtener credenciales kubectl
gcloud container clusters get-credentials "$CLUSTER" \
  --region="$GCP_REGION" --project="$GCP_PROJECT"

# ── NOTA: Cloud SQL vs Postgres en cluster ────────────────────────────────────
# Por defecto los manifests incluyen Postgres como Deployment dentro del cluster.
# Para usar Cloud SQL (creado por OpenTofu en gcs-computer-vision-infra):
#   1. Asegurate que DATABASE_URL en secret.yaml apunte a cloud-sql-proxy:5432
#   2. Agregá el Cloud SQL Auth Proxy como sidecar o Deployment separado.
#   3. Podés comentar services/postgres/ en kustomization.yaml.
# ─────────────────────────────────────────────────────────────────────────────

# Habilitar pull de imágenes desde ghcr.io (público, no requiere config extra)
# Si las imágenes son privadas, agregar imagePullSecrets en los deployments.

# ── Secrets ───────────────────────────────────────────────────────────────────
echo "→ Aplicando secrets..."
kubectl apply -f "$SECRET_FILE"

# ── Manifests ─────────────────────────────────────────────────────────────────
echo "→ Aplicando manifests (kubectl apply -k)..."
kubectl apply -k "$K8S_DIR"

# ── Esperar deployments core ──────────────────────────────────────────────────
echo "→ Esperando deployments core (timeout 5 min)..."
for deploy in postgres kafka api-gateway model-registry; do
  kubectl rollout status deployment/"$deploy" -n cv-platform --timeout=300s
done

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo " Deploy GKE completado — Proyecto: $GCP_PROJECT"
echo "═══════════════════════════════════════════"
kubectl get pods     -n cv-platform
echo ""
kubectl get services -n cv-platform
echo ""
echo "Esperando IP pública del api-gateway (puede tardar ~1 min)..."
kubectl get service api-gateway -n cv-platform --watch &
WATCH_PID=$!
sleep 60
kill $WATCH_PID 2>/dev/null || true
echo ""
EXTERNAL_IP=$(kubectl get service api-gateway -n cv-platform \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pendiente")
echo "API Gateway: http://${EXTERNAL_IP}/health"
