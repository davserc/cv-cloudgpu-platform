from fastapi import APIRouter

from app.schemas import JobCreateRequest, JobStatusResponse

router = APIRouter()


@router.post("/", response_model=JobStatusResponse)
def create_job(payload: JobCreateRequest) -> JobStatusResponse:
    return JobStatusResponse(job_id="demo-job", status="queued")


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    return JobStatusResponse(job_id=job_id, status="unknown")
