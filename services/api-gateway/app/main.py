from fastapi import FastAPI

from app.api.v1 import routes_infer, routes_models, routes_train
from app.schemas import HealthResponse

app = FastAPI(title="API Gateway", version="0.1.0")

app.include_router(routes_train.router, prefix="/api/v1/train", tags=["train"])
app.include_router(routes_models.router, prefix="/api/v1/models", tags=["models"])
app.include_router(routes_infer.router, prefix="/api/v1/infer", tags=["infer"])


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
