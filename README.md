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

## Estado
Estructura base. Los servicios y scripts se completarán incrementalmente.
