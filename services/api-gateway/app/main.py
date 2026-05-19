import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import routes_infer, routes_models, routes_train
from app.schemas import HealthResponse
from app.security import require_api_key

app = FastAPI(title="API Gateway", version="0.1.0")

# CORS — en prod restringir CORS_ALLOW_ORIGINS a los dominios del frontend
_raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
_origins = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app, include_in_schema=False)

protected = [Depends(require_api_key)]
app.include_router(
    routes_train.router, prefix="/api/v1/train", tags=["train"], dependencies=protected
)
app.include_router(
    routes_models.router, prefix="/api/v1/models", tags=["models"], dependencies=protected
)
app.include_router(
    routes_infer.router, prefix="/api/v1/infer", tags=["infer"], dependencies=protected
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
