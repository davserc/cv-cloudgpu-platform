# Resetea el offset del training-worker al ultimo mensaje y lo reinicia.
# Uso: .\infra\k8s\scripts\reset-worker.ps1
param(
    [string]$Group     = "training-service",
    [string]$Topic     = "training-jobs",
    [string]$Namespace = "cv-platform",
    [string]$Cluster   = "cv-platform"
)

$ErrorActionPreference = "Stop"

function Log { param($msg) Write-Host "-> $msg" -ForegroundColor Cyan }
function Ok  { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Die { param($msg) Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

# ── Buscar pod de Kafka ───────────────────────────────────────────────────────
Log "Buscando pod de Kafka..."
$kafkaPod = docker exec "$Cluster-control-plane" kubectl get pods -n $Namespace -l app=kafka -o jsonpath="{.items[0].metadata.name}" 2>$null
if (-not $kafkaPod) { Die "No se encontro pod de Kafka en namespace '$Namespace'." }
Ok "Kafka pod: $kafkaPod"

# ── Bajar el worker ───────────────────────────────────────────────────────────
Log "Bajando training-worker a 0 replicas..."
docker exec "$Cluster-control-plane" kubectl scale deployment/training-worker -n $Namespace --replicas=0
if ($LASTEXITCODE -ne 0) { Die "No se pudo bajar el worker." }

Log "Esperando que el worker termine..."
docker exec "$Cluster-control-plane" kubectl wait --for=delete pod -l app=training-worker -n $Namespace --timeout=90s 2>$null
# Ignorar timeout — verificar que no haya pods running antes de seguir
$attempts = 0
do {
    Start-Sleep -Seconds 3
    $running = ""
    try { $running = docker exec "$Cluster-control-plane" kubectl get pods -l app=training-worker -n $Namespace --no-headers 2>$null } catch {}
    $attempts++
} while ($running -and $attempts -lt 20)

# ── Resetear offset ───────────────────────────────────────────────────────────
Log "Reseteando offset del grupo '$Group' al ultimo mensaje..."
$resetCmd = "kafka-consumer-groups --bootstrap-server localhost:9092 --group $Group --topic $Topic --reset-offsets --to-latest --execute"
docker exec "$Cluster-control-plane" kubectl exec -n $Namespace $kafkaPod -- bash -c $resetCmd
if ($LASTEXITCODE -ne 0) { Die "No se pudo resetear el offset." }
Ok "Offset reseteado."

# ── Volver a levantar el worker ───────────────────────────────────────────────
Log "Levantando training-worker..."
docker exec "$Cluster-control-plane" kubectl scale deployment/training-worker -n $Namespace --replicas=1
if ($LASTEXITCODE -ne 0) { Die "No se pudo levantar el worker." }

docker exec "$Cluster-control-plane" kubectl rollout status deployment/training-worker -n $Namespace --timeout=60s
Ok "training-worker listo."

Write-Host ""
Write-Host "Ahora envia el job y seguilo con:" -ForegroundColor Yellow
Write-Host "  docker exec $Cluster-control-plane kubectl logs -n $Namespace deployment/training-worker -f"
