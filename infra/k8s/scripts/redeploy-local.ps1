# Rebuild y redeploy de todos los servicios en el cluster kind local.
# Uso: .\infra\k8s\scripts\redeploy-local.ps1 [-Service <nombre>]
#   Sin -Service => rebuild y redeploy de todos los servicios.
#   Con -Service  => solo ese servicio (api-gateway | model-registry | training-service | evaluation-service).
param(
    [string]$Service = "all"
)

$ErrorActionPreference = "Stop"

$CLUSTER    = "cv-platform"
$NAMESPACE  = "cv-platform"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PLATFORM_ROOT = (Resolve-Path "$SCRIPT_DIR\..\..\..").Path
$REPO_ROOT     = (Resolve-Path "$PLATFORM_ROOT\..").Path
$DB_URL = "postgresql+psycopg2://sauron:wingardium-leviosa@136.113.178.46:5432/computer-vision"

function Log  { param($msg) Write-Host "-> $msg" -ForegroundColor Cyan }
function Ok   { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Die  { param($msg) Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

function Invoke-Kubectl {
    docker exec "$CLUSTER-control-plane" kubectl @args
    if ($LASTEXITCODE -ne 0) { Die "kubectl falló: kubectl $args" }
}

# ── Checks ────────────────────────────────────────────────────────────────────
try { kind version | Out-Null } catch { Die "kind no encontrado. Instalá: https://kind.sigs.k8s.io/" }
try { docker info  | Out-Null } catch { Die "docker no encontrado o no está corriendo." }

$clusters = kind get clusters 2>$null
if ($clusters -notmatch "^$CLUSTER$") {
    Die "Cluster '$CLUSTER' no existe. Ejecutá deploy-local.sh primero."
}

# ── Helpers ───────────────────────────────────────────────────────────────────
function Build-And-Load {
    param([string]$Name, [string]$Dockerfile, [string]$Context)
    $tag = "${Name}:local"
    Log "Build $tag ..."
    docker build -f $Dockerfile -t $tag $Context
    if ($LASTEXITCODE -ne 0) { Die "docker build falló para $Name" }
    Log "Cargando $tag en kind '$CLUSTER'..."
    kind load docker-image $tag --name $CLUSTER
    if ($LASTEXITCODE -ne 0) { Die "kind load falló para $tag" }
    Ok "$tag listo."
}

function Patch-Deployment {
    param([string]$Deploy, [string]$Container, [string]$Image)
    Log "Patcheando $Deploy -> $Image ..."
    docker exec "$CLUSTER-control-plane" kubectl set image "deployment/$Deploy" "${Container}=${Image}" -n $NAMESPACE
    if ($LASTEXITCODE -ne 0) { Die "kubectl set image falló para $Deploy" }
    # Pasar el JSON por stdin para evitar problemas de quoting PowerShell -> docker exec
    $patch = '{"spec":{"template":{"spec":{"containers":[{"name":"' + $Container + '","imagePullPolicy":"IfNotPresent"}]}}}}'
    $patch | docker exec -i "$CLUSTER-control-plane" kubectl patch deployment $Deploy -n $NAMESPACE --patch-file /dev/stdin
    if ($LASTEXITCODE -ne 0) { Die "kubectl patch falló para $Deploy" }
}

function Restart-And-Wait {
    param([string]$Deploy)
    Log "Forzando rollout restart de $Deploy..."
    docker exec "$CLUSTER-control-plane" kubectl rollout restart "deployment/$Deploy" -n $NAMESPACE
    docker exec "$CLUSTER-control-plane" kubectl rollout status "deployment/$Deploy" -n $NAMESPACE --timeout=120s
    if ($LASTEXITCODE -ne 0) { Die "Rollout de $Deploy no terminó a tiempo." }
}

# ── Migraciones ───────────────────────────────────────────────────────────────
function Run-Migrations {
    Log "Buildeando imagen de migraciones..."
    docker build -f "$PLATFORM_ROOT\infra\db\Dockerfile" -t cv-migrate $PLATFORM_ROOT
    if ($LASTEXITCODE -ne 0) { Die "docker build para migraciones falló" }
    Log "Aplicando migraciones Alembic..."
    docker run --rm -e "DATABASE_URL=$DB_URL" cv-migrate alembic -c infra/db/alembic.ini upgrade head
    if ($LASTEXITCODE -ne 0) { Die "Alembic upgrade falló" }
    Ok "Migraciones aplicadas."
}

# ── Servicios ─────────────────────────────────────────────────────────────────
function Deploy-ApiGateway {
    Build-And-Load "api-gateway" "$PLATFORM_ROOT\services\api-gateway\Dockerfile" $PLATFORM_ROOT
    Patch-Deployment "api-gateway" "api-gateway" "api-gateway:local"
    Restart-And-Wait "api-gateway"
}

function Deploy-ModelRegistry {
    Build-And-Load "model-registry" "$PLATFORM_ROOT\services\model-registry\Dockerfile" $PLATFORM_ROOT
    Patch-Deployment "model-registry"        "model-registry"        "model-registry:local"
    Patch-Deployment "model-registry-worker" "model-registry-worker" "model-registry:local"
    Restart-And-Wait "model-registry"
    Restart-And-Wait "model-registry-worker"
}

function Deploy-TrainingService {
    Build-And-Load "training-service" "$PLATFORM_ROOT\services\training-service\Dockerfile" $REPO_ROOT
    Patch-Deployment "training-service" "training-service" "training-service:local"
    Patch-Deployment "training-worker"  "training-worker"  "training-service:local"
    Restart-And-Wait "training-service"
    Restart-And-Wait "training-worker"
}

function Deploy-EvaluationService {
    Build-And-Load "evaluation-service" "$PLATFORM_ROOT\services\evaluation-service\Dockerfile" $PLATFORM_ROOT
    Patch-Deployment "evaluation-service" "evaluation-service" "evaluation-service:local"
    Patch-Deployment "evaluation-worker"  "evaluation-worker"  "evaluation-service:local"
    Restart-And-Wait "evaluation-service"
    Restart-And-Wait "evaluation-worker"
}

# ── Main ──────────────────────────────────────────────────────────────────────
switch ($Service) {
    "all" {
        Run-Migrations
        Deploy-ApiGateway
        Deploy-ModelRegistry
        Deploy-TrainingService
        Deploy-EvaluationService
    }
    "api-gateway"        { Run-Migrations; Deploy-ApiGateway }
    "model-registry"     { Deploy-ModelRegistry }
    "training-service"   { Run-Migrations; Deploy-TrainingService }
    "evaluation-service" { Deploy-EvaluationService }
    default { Die "Servicio desconocido: '$Service'. Opciones: all | api-gateway | model-registry | training-service | evaluation-service" }
}

Write-Host ""
Write-Host "===========================================" -ForegroundColor Green
Write-Host " Redeploy completado" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green
Invoke-Kubectl get pods -n $NAMESPACE
Write-Host ""
Write-Host "Para acceder al API Gateway:" -ForegroundColor Yellow
Write-Host "  kubectl port-forward svc/api-gateway 8080:80 -n $NAMESPACE"
