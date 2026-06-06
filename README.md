# cv-cloudgpu-platform

Monorepo de microservicios para entrenamiento, registro, evaluación y serving de modelos de visión por computadora sobre GPU en la nube (Vast.ai).

## Arquitectura

```
cv-platform-ui  →  api-gateway  →  Kafka  →  training-worker
                              ↘  model-registry
                              ↘  model-serving
```

| Servicio | Puerto | Descripción |
|---|---|---|
| `api-gateway` | 8000 | Punto de entrada, autenticación, proxy |
| `training-service` | — | API de jobs (stub); worker consume Kafka |
| `training-worker` | — | Ejecuta entrenamiento en Vast.ai |
| `model-registry` | 8000 | Registro de versiones de modelos |
| `model-serving` | 8000 | Inferencia YOLO (JSON y PNG anotado) |
| `evaluation-service` | — | Evaluación automática post-training |

## Estructura

```
services/           microservicios
libs/common/        DB schema, session SQLAlchemy compartido
libs/contracts/     Eventos Kafka (TrainingJobEvent, ModelTrainedEvent)
infra/k8s/          Manifiestos Kubernetes
```

## Requisitos

### Local
- Docker Desktop con kind
- `kubectl`, `kind`
- Python 3.11+

### Producción (GKE vía OpenTofu)
- GCP project con APIs habilitadas (GKE, Cloud SQL, Secret Manager, GCS)
- `gcloud` CLI autenticado
- OpenTofu >= 1.6 — ver [`gcs-computer-vision-infra`](../gcs-computer-vision-infra)

## Deploy local (kind)

### 1. Crear cluster

```bash
kind create cluster --name cv-platform --config infra/k8s/kind-config.yaml
```

### 2. Construir y cargar imágenes locales

Las imágenes usan `imagePullPolicy: Never` — se cargan directamente en el nodo kind.

```bash
# Desde la raíz del monorepo (d:\Diplomatura-IA\TpFinal4)
docker build -f cv-cloudgpu-platform/services/api-gateway/Dockerfile \
  -t api-gateway:local cv-cloudgpu-platform/
kind load docker-image api-gateway:local --name cv-platform

docker build -f cv-cloudgpu-platform/services/training-service/Dockerfile \
  -t training-service:local .
kind load docker-image training-service:local --name cv-platform

docker build -f cv-cloudgpu-platform/services/model-serving/app/Dockerfile \
  -t cv-model-serving:local cv-cloudgpu-platform/
kind load docker-image cv-model-serving:local --name cv-platform
```

### 3. Aplicar manifiestos

```bash
kubectl apply -k infra/k8s/
```

### 4. Port-forward para acceso local

```bash
kubectl port-forward svc/api-gateway 8080:8000 -n cv-platform
# UI → http://localhost:5173  (npm run dev en cv-platform-ui/)
```

### Actualizar un servicio tras cambios

```bash
docker build ... -t <imagen>:local .
kind load docker-image <imagen>:local --name cv-platform
kubectl rollout restart deployment/<nombre> -n cv-platform
```

> `kubectl rollout restart deploy -n cv-platform` reinicia **todos** los deployments.
> No descarga imágenes nuevas — solo usa las ya cargadas con `kind load`.

## Deploy en producción (GKE)

El deploy en producción es gestionado por el módulo OpenTofu en [`gcs-computer-vision-infra`](../gcs-computer-vision-infra).

Ese módulo:
1. Crea la infraestructura GCP (GKE, Cloud SQL, GCS, Secret Manager)
2. Sube el bundle de la app al bucket
3. La VM aplica los manifiestos Kubernetes al iniciar

Para hacer un re-deploy después de cambios en el código:

```bash
# Desde la raíz del monorepo — regenerar el bundle
tar -czf app_bundle.tar.gz cv-cloudgpu-platform/

# Subir el bundle al bucket GCS
gsutil cp app_bundle.tar.gz gs://<bucket>/app_bundle.tar.gz

# Volver a aplicar OpenTofu para que la VM lo tome
cd ../gcs-computer-vision-infra/opentofu/dev
tofu apply
```

## Observabilidad

El stack de observabilidad (Grafana + Loki + Prometheus) corre **dentro del cluster Kubernetes**, no en una VM separada.

```bash
# Ver pods de monitoreo
kubectl get pods -n monitoring

# Port-forward a Grafana
kubectl port-forward svc/grafana 3000:3000 -n monitoring

# Acceder en http://localhost:3000
```

LogQL para filtrar por servicio en Grafana:
```
{container="api-gateway"}
{container="training-worker"}
{container="model-serving"}
```

## Variables de entorno / Secrets

El Secret `cv-platform-secrets` debe contener:

| Clave | Descripción |
|---|---|
| `API_GATEWAY_API_KEY` | Clave para `X-API-KEY` header |
| `DATABASE_URL` | `postgresql+psycopg2://user:pass@postgres:5432/db` |
| `VAST_API_KEY` | Clave de Vast.ai |
| `VAST_SSH_PRIVATE_KEY` | Clave privada SSH para instancias Vast.ai |
| `GCP_SA_B64` | Service account GCP en base64 (para datasets GCS) |

> `secret.yaml` está en `.gitignore`. Usar el template `secret.yaml.tpl`.

## Entrenamiento en Vast.ai

El `training-worker` selecciona automáticamente la GPU más barata disponible, ejecuta el entrenamiento en dos fases (backbone frozen → full fine-tune) y descarga el artifact al PVC.

**Blacklist de offers problemáticas:**

```
/data/artifacts/.vast_offer_blacklist.json   (en el PVC, persiste entre reinicios)
```

TTL por defecto: 7 días (`VAST_OFFER_BLACKLIST_TTL_SEC=604800`).

Las ofertas con CUDA initialization bug se añaden automáticamente al blacklist al detectar `CUDA_NOT_AVAILABLE:` en el log. El worker reintenta hasta 3 veces (`TRAIN_MAX_CUDA_RETRIES=3`) eligiendo una GPU diferente cada vez.

**Checkpointing automático en GCS:**

Si se setea `TRAIN_CHECKPOINT_GCS_BASE_URI`, el worker sincroniza `/work/checkpoints/` con GCS durante el entrenamiento. Si la instancia se cae (timeout SSH, preemption, etc.) y el job se relanza con el mismo `job_id`, el training retoma desde el último checkpoint subido — sin modificar nada de la lógica existente.

| Variable | Descripción |
|---|---|
| `TRAIN_CHECKPOINT_GCS_BASE_URI` | URI base en GCS, ej. `gs://bucket/checkpoints`. Si no está seteada, el comportamiento es idéntico al original. |
| `TRAIN_CHECKPOINT_SYNC_INTERVAL_SEC` | Cada cuántos segundos se sincroniza a GCS (default: `300`) |

Flujo:
1. Al iniciar la instancia, descarga `{base}/{job_id}/` → `/work/checkpoints/`
2. `run_service.sh` detecta el checkpoint y pasa `--resume` automáticamente a YOLO
3. Cada 5 minutos, sube `/work/checkpoints/` a GCS en background
4. Al terminar (éxito o fallo), hace una sincronización final

Para activarlo, agregar al Secret o ConfigMap:
```yaml
TRAIN_CHECKPOINT_GCS_BASE_URI: "gs://unlu-genai-serranodavid-computer_vision_yolo/checkpoints"
```

## Inferencia

```bash
# JSON con detecciones
POST /api/v1/infer/upload          (multipart, devuelve JSON)

# Imagen PNG anotada con bounding boxes
POST /api/v1/infer/upload/annotated (multipart, devuelve PNG)
```

## Comandos útiles

```bash
kubectl get pods -n cv-platform
kubectl logs -n cv-platform deploy/training-worker -f
kubectl logs -n cv-platform deploy/api-gateway --tail=50
kubectl exec -n cv-platform deploy/training-worker -- cat .vast_offer_blacklist.json
kubectl rollout restart deploy -n cv-platform
```

## Estado

Sistema funcional end-to-end: envío de jobs → entrenamiento en Vast.ai → registro de modelo → inferencia con imagen anotada → UI con ranking de modelos por mAP50.
