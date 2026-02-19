import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter
from kafka import KafkaProducer
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.schemas import TrainRequest, TrainResponse
from contracts.events import TrainingJobEvent
from common.db import events, session_scope

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
        timestamp=datetime.now(timezone.utc).isoformat(),
        job_id=job_id,
        batch=payload.batch,
        device=payload.device,
        epochs=payload.epochs,
        imgsz=payload.imgsz,
        model=payload.model,
        name=payload.name,
        patience=payload.patience,
        project=payload.project,
        save=payload.save,
        config=None,
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
