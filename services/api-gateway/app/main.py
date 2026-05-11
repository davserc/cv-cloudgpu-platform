from fastapi import Depends, FastAPI

from app.api.v1 import routes_infer, routes_models, routes_train
from app.schemas import HealthResponse
from app.security import require_api_key

app = FastAPI(title="API Gateway", version="0.1.0")

protected = [Depends(require_api_key)]
app.include_router(routes_train.router, prefix="/api/v1/train", tags=["train"], dependencies=protected)
app.include_router(routes_models.router, prefix="/api/v1/models", tags=["models"], dependencies=protected)
app.include_router(routes_infer.router, prefix="/api/v1/infer", tags=["infer"], dependencies=protected)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
