#!/usr/bin/env bash
# Deploy cv-cloudgpu-platform locally using kind (Kubernetes in Docker).
# Prerequisites: kind, kubectl, Docker Desktop running.
#   kind:    https://kind.sigs.k8s.io/
#   kubectl: https://kubernetes.io/docs/tasks/tools/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$SCRIPT_DIR/.."
SECRET_FILE="$K8S_DIR/base/secret.yaml"
CLUSTER="cv-platform"

# ── Checks ────────────────────────────────────────────────────────────────────
command -v kind    >/dev/null || { echo "ERROR: kind not found.  Install: https://kind.sigs.k8s.io/"; exit 1; }
command -v kubectl >/dev/null || { echo "ERROR: kubectl not found."; exit 1; }
command -v docker  >/dev/null || { echo "ERROR: docker not found."; exit 1; }

if [[ ! -f "$SECRET_FILE" ]]; then
  echo "ERROR: $SECRET_FILE no existe."
  echo "  Copiá el template y completá los valores:"
  echo "  cp infra/k8s/base/secret.yaml.tpl infra/k8s/base/secret.yaml"
  exit 1
fi

# ── Cluster ───────────────────────────────────────────────────────────────────
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER}$"; then
  echo "✓ Cluster '$CLUSTER' ya existe."
else
  echo "→ Creando cluster kind '$CLUSTER'..."
  kind create cluster --name "$CLUSTER"
fi

kubectl config use-context "kind-${CLUSTER}"

# ── Secrets (fuera del kustomize para no commitearlos) ────────────────────────
echo "→ Aplicando secrets..."
kubectl apply -f "$SECRET_FILE"

# ── Manifests ─────────────────────────────────────────────────────────────────
echo "→ Aplicando manifests (kubectl apply -k)..."
kubectl apply -k "$K8S_DIR"

# ── Esperar deployments core ──────────────────────────────────────────────────
echo "→ Esperando que arranquen los deployments core..."
for deploy in postgres kafka api-gateway model-registry; do
  kubectl rollout status deployment/"$deploy" -n cv-platform --timeout=120s
done

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo " Deploy local completado"
echo "═══════════════════════════════════════════"
kubectl get pods     -n cv-platform
echo ""
kubectl get services -n cv-platform
echo ""
echo "API Gateway (port-forward para acceder local):"
echo "  kubectl port-forward svc/api-gateway 8080:80 -n cv-platform"
echo "  curl http://localhost:8080/health"
