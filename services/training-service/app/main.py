from fastapi import FastAPI

from app.api.v1 import routes_health, routes_jobs
from app.schemas import HealthResponse

app = FastAPI(title="Training Service", version="0.1.0")

app.include_router(routes_health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(routes_jobs.router, prefix="/api/v1/jobs", tags=["jobs"])


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
