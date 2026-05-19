#!/usr/bin/env bash
# Rebuild y redeploy de todos los servicios en el cluster kind local.
# Uso: bash infra/k8s/scripts/redeploy-local.sh [servicio]
#   Sin argumento => rebuild y redeploy de todos los servicios.
#   Con argumento => solo ese servicio (api-gateway | model-registry | training-service | evaluation-service).
set -euo pipefail

CLUSTER="cv-platform"
NAMESPACE="cv-platform"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../" && pwd)"
PLATFORM_ROOT="$REPO_ROOT/cv-cloudgpu-platform"

TARGET="${1:-all}"

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "→ $*"; }
ok()   { echo "✓ $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

kubectl_inner() { docker exec "${CLUSTER}-control-plane" kubectl "$@"; }

build_and_load() {
  local name="$1" dockerfile="$2" context="$3"
  local tag="${name}:local"
  log "Build $tag ..."
  docker build -f "$dockerfile" -t "$tag" "$context"
  log "Cargando $tag en kind '$CLUSTER'..."
  kind load docker-image "$tag" --name "$CLUSTER"
  ok "$tag listo."
}

patch_deployment() {
  local deploy="$1" container="$2" image="$3"
  log "Patcheando $deploy → $image ..."
  kubectl_inner set image "deployment/$deploy" "${container}=${image}" -n "$NAMESPACE"
  kubectl_inner patch deployment "$deploy" -n "$NAMESPACE" \
    -p "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"${container}\",\"imagePullPolicy\":\"IfNotPresent\"}]}}}}"
}

wait_rollout() {
  local deploy="$1"
  log "Esperando rollout de $deploy..."
  kubectl_inner rollout status "deployment/$deploy" -n "$NAMESPACE" --timeout=120s
}

# ── Migraciones ───────────────────────────────────────────────────────────────
# Las migraciones corren como Job dentro del cluster para poder alcanzar
# postgres via el service name (postgres:5432). DATABASE_URL viene del secret.
run_migrations() {
  log "Buildeando imagen de migraciones..."
  docker build -f "$PLATFORM_ROOT/infra/db/Dockerfile" -t cv-migrate:local "$PLATFORM_ROOT"
  log "Cargando cv-migrate:local en kind '$CLUSTER'..."
  kind load docker-image cv-migrate:local --name "$CLUSTER"

  log "Eliminando job previo de migraciones (si existe)..."
  docker exec "${CLUSTER}-control-plane" \
    kubectl delete job db-migrate -n "$NAMESPACE" --ignore-not-found=true

  log "Lanzando Job de migraciones dentro del cluster..."
  docker exec -i "${CLUSTER}-control-plane" kubectl apply -n "$NAMESPACE" -f - << 'YAML'
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate
spec:
  ttlSecondsAfterFinished: 120
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: migrate
          image: cv-migrate:local
          imagePullPolicy: IfNotPresent
          command: ["alembic", "-c", "infra/db/alembic.ini", "upgrade", "head"]
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: cv-platform-secrets
                  key: DATABASE_URL
YAML

  log "Esperando que el Job de migraciones complete..."
  docker exec "${CLUSTER}-control-plane" \
    kubectl wait job/db-migrate -n "$NAMESPACE" --for=condition=complete --timeout=120s

  log "Logs de migraciones:"
  docker exec "${CLUSTER}-control-plane" \
    kubectl logs job/db-migrate -n "$NAMESPACE"

  ok "Migraciones aplicadas."
}

# ── Definición de servicios ───────────────────────────────────────────────────
deploy_api_gateway() {
  build_and_load "api-gateway" \
    "$PLATFORM_ROOT/services/api-gateway/Dockerfile" \
    "$PLATFORM_ROOT"
  patch_deployment "api-gateway" "api-gateway" "api-gateway:local"
  wait_rollout "api-gateway"
}

deploy_model_registry() {
  build_and_load "model-registry" \
    "$PLATFORM_ROOT/services/model-registry/Dockerfile" \
    "$PLATFORM_ROOT"
  patch_deployment "model-registry"        "model-registry"        "model-registry:local"
  patch_deployment "model-registry-worker" "model-registry-worker" "model-registry:local"
  wait_rollout "model-registry"
  wait_rollout "model-registry-worker"
}

deploy_training_service() {
  build_and_load "training-service" \
    "$PLATFORM_ROOT/services/training-service/Dockerfile" \
    "$REPO_ROOT"
  patch_deployment "training-service" "training-service" "training-service:local"
  patch_deployment "training-worker"  "training-worker"  "training-service:local"
  wait_rollout "training-service"
  wait_rollout "training-worker"
}

deploy_evaluation_service() {
  build_and_load "evaluation-service" \
    "$PLATFORM_ROOT/services/evaluation-service/Dockerfile" \
    "$PLATFORM_ROOT"
  patch_deployment "evaluation-service" "evaluation-service" "evaluation-service:local"
  patch_deployment "evaluation-worker"  "evaluation-worker"  "evaluation-service:local"
  wait_rollout "evaluation-service"
  wait_rollout "evaluation-worker"
}

# ── Main ──────────────────────────────────────────────────────────────────────
kind version >/dev/null 2>&1   || die "kind no encontrado. Instalá: https://kind.sigs.k8s.io/"
docker info  >/dev/null 2>&1   || die "docker no encontrado o no está corriendo."
kind get clusters 2>/dev/null | grep -q "^${CLUSTER}$" || die "Cluster '$CLUSTER' no existe. Ejecutá deploy-local.sh primero."

case "$TARGET" in
  all)
    run_migrations
    deploy_api_gateway
    deploy_model_registry
    deploy_training_service
    deploy_evaluation_service
    ;;
  api-gateway)        run_migrations; deploy_api_gateway ;;
  model-registry)     deploy_model_registry ;;
  training-service)   run_migrations; deploy_training_service ;;
  evaluation-service) deploy_evaluation_service ;;
  *)
    die "Servicio desconocido: '$TARGET'. Opciones: all | api-gateway | model-registry | training-service | evaluation-service"
    ;;
esac

echo ""
echo "═══════════════════════════════════════════"
echo " Redeploy completado"
echo "═══════════════════════════════════════════"
kubectl_inner get pods -n "$NAMESPACE"
echo ""
echo "Para acceder al API Gateway:"
echo "  kubectl port-forward svc/api-gateway 8080:80 -n $NAMESPACE"
