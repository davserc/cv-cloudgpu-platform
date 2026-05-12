                                                                                                                                                    # DiplomaturaIA-Computer-Vision

Monorepo para una arquitectura de microservicios con FastAPI orientada a entrenamiento, evaluación, registro y serving de modelos de visión por computadora.

## Estructura
- `services/` microservicios (gateway, training, evaluation, registry, serving)
- `libs/` librerías compartidas (common, contracts, ml)
- `infra/` docker/k8s
- `docs/` documentación y OpenAPI
- `storage/` almacenamiento local de desarrollo

## Requisitos
- Python 3.10+ (recomendado 3.11)
- Docker (para servicios de infraestructura local)

## Flujo (alto nivel)
1. El gateway recibe solicitudes.
2. Training genera un modelo y publica evento.
3. Evaluation calcula métricas y publica evento.
4. Model Registry guarda versiones/estados.
5. Serving descarga artefactos y responde inferencias.

## Uso rápido (local)
Ver `docs/runbooks/local.md` y `infra/docker/docker-compose.local.yml`.

Variables de base de datos para local (`.env.develop`):
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `API_GATEWAY_API_KEY` (required for `/api/v1/train`, `/api/v1/infer`, `/api/v1/models`)

`DATABASE_URL` se construye en runtime a partir de esas variables. No versionar credenciales reales.

Seguridad API:
- Enviar header `X-API-Key: <API_GATEWAY_API_KEY>` en endpoints públicos.
- Sin credencial o con credencial inválida el gateway responde `401/403`.

### Base de datos local (automatizado)

1. Ejecutar todo en un paso:
   - `powershell -ExecutionPolicy Bypass -File scripts/local-dev-up.ps1`
2. Bajar DB local:
   - `powershell -ExecutionPolicy Bypass -File scripts/local-db-down.ps1`

Opciones:
- Sobrescribir `.env.develop` desde template:
  - `powershell -ExecutionPolicy Bypass -File scripts/local-dev-up.ps1 -ForceEnv`
- Levantar sin rebuild de imágenes:
  - `powershell -ExecutionPolicy Bypass -File scripts/local-dev-up.ps1 -SkipBuild`

## Deploy con Kubernetes

Los manifiestos están en `infra/k8s/`. Se aplican con Kustomize (`kubectl apply -k`).

### Prerequisito: crear el Secret con valores reales

```bash
cp infra/k8s/base/secret.yaml.tpl infra/k8s/base/secret.yaml
# editar secret.yaml con DB_USER, DB_PASSWORD, DATABASE_URL, VAST_API_KEY, etc.
```

> `secret.yaml` está en `.gitignore` — nunca se commitea.

### Opción A — Local con kind

```bash
# Requisitos: kind, kubectl, Docker corriendo
bash infra/k8s/scripts/deploy-local.sh

# Acceder al api-gateway:
kubectl port-forward svc/api-gateway 8080:80 -n cv-platform
curl http://localhost:8080/health
```

### Opción B — GKE (Google Kubernetes Engine)

```bash
# Requisitos: gcloud CLI autenticado, kubectl
export GCP_PROJECT=project-38c56a6f-24a9-45fb-aef
bash infra/k8s/scripts/deploy-gke.sh
```

El script crea el cluster, obtiene credenciales y aplica todos los manifiestos.
La IP pública del api-gateway aparece al finalizar.

> Para usar Cloud SQL en vez del Postgres en cluster: actualizá `DATABASE_URL`
> en `secret.yaml` para apuntar a `cloud-sql-proxy:5432`.

### Comandos útiles post-deploy

```bash
kubectl get pods     -n cv-platform          # estado de pods
kubectl get services -n cv-platform          # IPs y puertos
kubectl logs -n cv-platform deploy/api-gateway   # logs
kubectl rollout restart deploy -n cv-platform    # redeploy con nueva imagen
```

## Estado
Estructura base. Los servicios y scripts se completarán incrementalmente.
