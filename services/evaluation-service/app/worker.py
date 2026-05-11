import json
import logging
import os
import signal
import sys
import time
from datetime import UTC, datetime
from uuid import uuid4

from kafka import KafkaConsumer, KafkaProducer
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from common.db import eval_reports, events, model_versions, session_scope
from contracts.events import ModelEvaluatedEvent, ModelTrainedEvent

logger = logging.getLogger(__name__)


def build_consumer() -> KafkaConsumer:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.getenv("KAFKA_TOPIC", "model-trained")
    group_id = os.getenv("KAFKA_GROUP_ID", "evaluation-service")

    return KafkaConsumer(
        topic,
        bootstrap_servers=[s.strip() for s in bootstrap.split(",") if s.strip()],
        group_id=group_id,
        auto_offset_reset=os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
        enable_auto_commit=True,
        value_deserializer=lambda v: v.decode("utf-8") if v else "",
    )


def build_producer() -> KafkaProducer:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    return KafkaProducer(
        bootstrap_servers=[s.strip() for s in bootstrap.split(",") if s.strip()],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    consumer = build_consumer()
    producer = build_producer()
    output_topic = os.getenv("KAFKA_OUTPUT_TOPIC", "model-evaluated")

    def handle_shutdown(signum, frame) -> None:
        logger.info("worker.shutdown signal=%s", signum)
        try:
            consumer.close()
            producer.flush(5)
            producer.close()
        finally:
            sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info(
        "worker.start topic=%s output_topic=%s",
        os.getenv("KAFKA_TOPIC", "model-trained"),
        output_topic,
    )

    while True:
        records = consumer.poll(timeout_ms=1000)
        if not records:
            time.sleep(0.5)
            continue

        for _, messages in records.items():
            for msg in messages:
                payload = msg.value
                try:
                    data = json.loads(payload) if payload else {}
                    event = ModelTrainedEvent.model_validate(data)
                except Exception as exc:
                    logger.warning("worker.invalid_message offset=%s error=%s", msg.offset, exc)
                    continue

                logger.info("worker.message offset=%s model_id=%s", msg.offset, event.model_id)
                # TODO: ejecutar evaluación real con event

                evaluated_event = ModelEvaluatedEvent(
                    event_id=str(uuid4()),
                    timestamp=datetime.now(UTC).isoformat(),
                    model_id=event.model_id,
                    report_uri=os.getenv("REPORT_URI", "s3://bucket/reports/report.json"),
                    metrics={"mAP": 0.0},
                )

                with session_scope() as session:
                    version_id = session.execute(
                        select(model_versions.c.id)
                        .where(model_versions.c.model_id == event.model_id)
                        .order_by(model_versions.c.updated_at.desc())
                        .limit(1)
                    ).scalar()
                    if version_id:
                        session.execute(
                            pg_insert(eval_reports).values(
                                model_version_id=version_id,
                                report_uri=evaluated_event.report_uri,
                                metrics_json=evaluated_event.metrics,
                            )
                        )
                        session.execute(
                            update(model_versions)
                            .where(model_versions.c.id == version_id)
                            .values(
                                metrics_json=evaluated_event.metrics, updated_at=datetime.now(UTC)
                            )
                        )
                    session.execute(
                        pg_insert(events).values(
                            service="evaluation-service",
                            event_type=evaluated_event.event_type,
                            payload_json=evaluated_event.model_dump(),
                        )
                    )

                producer.send(output_topic, evaluated_event.model_dump())
                producer.flush()
                logger.info(
                    "worker.published event=%s model_id=%s",
                    evaluated_event.event_type,
                    evaluated_event.model_id,
                )


if __name__ == "__main__":
    run()
