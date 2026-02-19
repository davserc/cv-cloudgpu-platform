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

## Estado
Estructura base. Los servicios y scripts se completarán incrementalmente.
