# training-service

Servicio de entrenamiento de modelos YOLO sobre GPU en la nube (Vast.ai).

## Componentes

| Módulo | Descripción |
|---|---|
| `app/main.py` | FastAPI con endpoints de jobs (stub) |
| `app/worker.py` | Consumer Kafka — procesa `training-jobs` |
| `app/vast_runner.py` | Orquesta ejecución en Vast.ai |
| `app/training.py` | Construye el comando de entrenamiento (2 fases) |
| `app/metrics.py` | Parsea métricas YOLO del log (`mAP50`, `box_p`, etc.) |
| `app/db_ops.py` | Operaciones sobre `training_runs` en PostgreSQL |

## Flujo del worker

```
Kafka (training-jobs)
  → seleccionar GPU en Vast.ai (cheapest offer no blacklisteada)
  → descargar dataset (GCS o HTTP)
  → ejecutar run_service.sh en modo detached
  → polling del status cada 15s + descarga periódica del log
  → descargar artifact (best.pt / last.pt)
  → destruir instancia
  → parsear métricas del log
  → publicar ModelTrainedEvent en Kafka (model-trained)
```

## Recuperación ante fallos CUDA

Si el log contiene `CUDA_NOT_AVAILABLE:`:
1. La offer se añade al blacklist (`/data/artifacts/.vast_offer_blacklist.json`)
2. El job se re-encola automáticamente (hasta `TRAIN_MAX_CUDA_RETRIES=3`)
3. El siguiente intento usa una GPU diferente

## Variables de entorno clave

| Variable | Default | Descripción |
|---|---|---|
| `KAFKA_TOPIC` | `training-jobs` | Topic de entrada |
| `KAFKA_OUTPUT_TOPIC` | `model-trained` | Topic de salida |
| `TRAIN_LOG_DIR` | `/data/artifacts` | Directorio de logs |
| `VAST_OFFER_BLACKLIST_PATH` | `/data/artifacts/.vast_offer_blacklist.json` | Blacklist persistente |
| `VAST_OFFER_BLACKLIST_TTL_SEC` | `604800` | TTL del blacklist (7 días) |
| `TRAIN_MAX_CUDA_RETRIES` | `3` | Máximo de reintentos por CUDA error |
| `VAST_MAX_LAUNCH_ATTEMPTS` | `5` | Intentos de launch por run |
| `VAST_MAX_PRICE` | _(sin límite)_ | Precio máximo por hora en Vast.ai ($/hr) |
| `VAST_MIN_CUDA` | _(cualquiera)_ | Versión mínima de CUDA requerida |

## Configuración de GPU (solo admins)

`VAST_MAX_PRICE` y `VAST_MIN_CUDA` afectan directamente el presupuesto de Vast.ai y **solo deben ser modificadas por administradores** con acceso al cluster.

```bash
# Cambiar límites de GPU (requiere acceso kubectl)
kubectl set env deployment/training-worker -n cv-platform \
  VAST_MAX_PRICE=1.50 \
  VAST_MIN_CUDA=7.5

# Ver configuración actual
kubectl exec -n cv-platform deploy/training-worker -- \
  env | grep VAST_
```

> Estas variables no están expuestas en el frontend. Cualquier valor enviado por el cliente es ignorado.

## Imagen Docker

```bash
# Construir desde la raíz del monorepo (TpFinal4/)
docker build -f cv-cloudgpu-platform/services/training-service/Dockerfile \
  -t training-service:local .
kind load docker-image training-service:local --name cv-platform
kubectl rollout restart deployment/training-worker -n cv-platform
```

## Endpoints API

| Método | Path | Descripción |
|---|---|---|
| `GET` | `/api/v1/train/recent` | Jobs recientes con estado real de DB |
| `GET` | `/api/v1/train/running` | Jobs actualmente en ejecución |
| `GET` | `/api/v1/train/{job_id}/logs` | Log de entrenamiento (hasta 100 KB) |
| `POST` | `/api/v1/train/` | Encolar nuevo job |
