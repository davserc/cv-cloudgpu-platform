import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from kafka import KafkaProducer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.schemas import JobStatus, RecentJobsResponse, RunningJobsResponse, TrainLogResponse, TrainRequest, TrainResponse
from common.db import events, session_scope, training_runs
from contracts.events import TrainingJobEvent

router = APIRouter()


def build_producer() -> KafkaProducer:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    return KafkaProducer(
        bootstrap_servers=[s.strip() for s in bootstrap.split(",") if s.strip()],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


@router.post(
    "/",
    response_model=TrainResponse,
    summary="Queue a training job",
    description="Publish a training job to Kafka. Returns a job_id.",
)
def submit_training_job(payload: TrainRequest) -> TrainResponse:
    job_id = payload.job_id or str(uuid4())
    event = TrainingJobEvent(
        event_id=str(uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        job_id=job_id,
        config=payload.config,
    )

    producer = build_producer()
    topic = os.getenv("KAFKA_TOPIC", "training-jobs")
    producer.send(topic, event.model_dump())
    producer.flush()
    producer.close()

    with session_scope() as session:
        session.execute(
            pg_insert(events).values(
                service="api-gateway",
                event_type=event.event_type,
                payload_json=event.model_dump(),
                correlation_id=job_id,
            )
        )

    return TrainResponse(status="queued", job_id=job_id)


@router.get(
    "/recent",
    response_model=RecentJobsResponse,
    summary="Get recent training jobs with their status",
)
def get_recent_training_jobs(limit: int = 50) -> RecentJobsResponse:
    stmt = (
        select(
            training_runs.c.job_id,
            training_runs.c.status,
            training_runs.c.started_at,
            training_runs.c.finished_at,
            training_runs.c.metrics_json,
        )
        .order_by(training_runs.c.started_at.desc())
        .limit(limit)
    )
    with session_scope() as session:
        rows = session.execute(stmt).mappings().all()
    items = [
        JobStatus(
            job_id=row["job_id"],
            status=row["status"] or "unknown",
            started_at=row["started_at"].isoformat() if row["started_at"] else None,
            finished_at=row["finished_at"].isoformat() if row["finished_at"] else None,
            error=(row["metrics_json"] or {}).get("error"),
        )
        for row in rows
    ]
    return RecentJobsResponse(items=items)


@router.get(
    "/running",
    response_model=RunningJobsResponse,
    summary="Get currently running training jobs",
)
def get_running_training_jobs() -> RunningJobsResponse:
    # Exclude jobs running longer than the stale timeout — belt-and-suspenders
    # guard for jobs whose worker died before calling record_training_end.
    # The worker also reconciles stale rows at startup; this filter covers the
    # window between a crash and the next worker restart.
    stale_timeout_h = int(os.getenv("TRAIN_STALE_TIMEOUT_HOURS", "12"))
    cutoff = datetime.now(UTC) - timedelta(hours=stale_timeout_h)
    stmt = select(training_runs.c.job_id).where(
        training_runs.c.status == "running",
        training_runs.c.started_at > cutoff,
    )
    with session_scope() as session:
        rows = session.execute(stmt).all()
    running_job_ids = [row[0] for row in rows if row and row[0]]
    return RunningJobsResponse(active=len(running_job_ids) > 0, running_job_ids=running_job_ids)


@router.get(
    "/{job_id}/logs",
    response_model=TrainLogResponse,
    summary="Get training job logs",
    description="Returns the current content of the training log for a job. "
    "The log is updated periodically while training is running.",
)
def get_training_logs(job_id: str) -> TrainLogResponse:
    log_dir = Path(os.getenv("TRAIN_LOG_DIR", "/data/artifacts"))
    log_path = log_dir / f"train_{job_id}.log"

    if not log_path.exists():
        return TrainLogResponse(job_id=job_id, log="", available=False)

    try:
        content = log_path.read_text(errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Cap at 100 KB to avoid huge responses
    max_bytes = 100_000
    if len(content) > max_bytes:
        content = content[-max_bytes:]

    return TrainLogResponse(job_id=job_id, log=content, available=True)
