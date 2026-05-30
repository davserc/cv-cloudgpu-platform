# api-gateway

Punto de entrada único de la plataforma. Valida la API key, enruta requests a los servicios internos y expone métricas Prometheus.

## Endpoints

### Training
| Método | Path | Descripción |
|---|---|---|
| `POST` | `/api/v1/train/` | Encolar job de entrenamiento |
| `GET` | `/api/v1/train/recent` | Jobs recientes con estado real (DB) |
| `GET` | `/api/v1/train/running` | Jobs actualmente en ejecución |
| `GET` | `/api/v1/train/{job_id}/logs` | Log de entrenamiento |

### Modelos
| Método | Path | Descripción |
|---|---|---|
| `GET` | `/api/v1/models/` | Listado con métricas (mAP50, precision, recall) |
| `GET` | `/api/v1/models/{model_id}` | Detalle de un modelo |
| `DELETE` | `/api/v1/models/{model_id}` | Eliminar modelo |

### Inferencia
| Método | Path | Descripción |
|---|---|---|
| `GET` | `/api/v1/infer/model` | Modelo activo |
| `POST` | `/api/v1/infer/upload` | Inferencia por archivo → JSON |
| `POST` | `/api/v1/infer/upload/annotated` | Inferencia por archivo → PNG anotado |

## Autenticación

Header requerido en todos los endpoints: `X-API-KEY: <valor>`.

El valor se configura en el Secret `cv-platform-secrets` bajo la clave `API_GATEWAY_API_KEY`. En la UI se carga desde la pantalla **Config**.

## Imagen Docker

```bash
cd cv-cloudgpu-platform/
docker build -f services/api-gateway/Dockerfile -t api-gateway:local .
kind load docker-image api-gateway:local --name cv-platform
kubectl rollout restart deployment/api-gateway -n cv-platform
```
