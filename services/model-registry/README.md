# model-registry

Registro de versiones de modelos. Almacena metadata, métricas y URIs de artifacts en PostgreSQL. Expone CRUD REST y consume el topic `model-trained` de Kafka para registrar modelos automáticamente al finalizar un entrenamiento.

## Endpoints

| Método | Path | Descripción |
|---|---|---|
| `GET` | `/api/v1/models/` | Listado de modelos (última versión de cada uno) |
| `GET` | `/api/v1/models/{model_id}` | Detalle con métricas y artifact_uri |
| `POST` | `/api/v1/models/` | Registrar modelo manualmente |
| `PATCH` | `/api/v1/models/{model_id}` | Actualizar status/métricas |
| `DELETE` | `/api/v1/models/{model_id}` | Eliminar modelo |

## Flujo automático

```
Kafka (model-trained)
  → model-registry-worker
  → upsert_model + upsert_model_version con métricas y artifact_uri
```

## Métricas registradas

Para modelos de segmentación YOLO (campo `metrics_json`):

```json
{
  "box_p": 0.315, "box_r": 0.226,
  "box_mAP50": 0.151, "box_mAP50_95": 0.0951,
  "mask_p": 0.31,  "mask_r": 0.22,
  "mask_mAP50": 0.14, "mask_mAP50_95": 0.0804,
  "mAP50": 0.14, "mAP": 0.0804
}
```

La UI ordena los modelos por `mAP50` descendente.
