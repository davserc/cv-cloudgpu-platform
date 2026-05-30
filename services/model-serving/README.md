# model-serving

Servicio de inferencia con modelos YOLO. Descarga el modelo del registro, lo carga en memoria y responde predicciones en JSON o imagen PNG anotada.

## Endpoints

| Método | Path | Descripción |
|---|---|---|
| `GET` | `/api/v1/infer/model` | Modelo activo (o por `?model_id=`) |
| `POST` | `/api/v1/infer/` | Inferencia por URI (GCS, HTTP, ruta local) |
| `POST` | `/api/v1/infer/upload` | Inferencia por upload multipart → JSON |
| `POST` | `/api/v1/infer/upload/annotated` | Inferencia por upload multipart → PNG anotado |

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `MODEL_CACHE_DIR` | `/data/models` | Caché local de pesos descargados |
| `INFER_UPLOAD_DIR` | `/data/artifacts/uploads` | Directorio de uploads temporales |
| `MODEL_REGISTRY_URL` | `http://model-registry:8000/api/v1/models` | URL del registro |

## Imagen Docker

```bash
docker build -f cv-cloudgpu-platform/services/model-serving/app/Dockerfile \
  -t cv-model-serving:local cv-cloudgpu-platform/
kind load docker-image cv-model-serving:local --name cv-platform
kubectl rollout restart deployment/model-serving -n cv-platform
```

## Notas

- El modelo se carga con `YOLO(path)` de ultralytics y se cachea en memoria por `model_id`.
- La imagen anotada usa `results[0].plot()` para escalar correctamente labels y cajas.
- El PVC `artifacts-pvc` se monta en `/data/artifacts` (compartido con training-worker).
