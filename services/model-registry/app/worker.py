import json
import logging
import os
import time

from kafka import KafkaConsumer

from app.db import upsert_model, upsert_model_version
from contracts.events import ModelTrainedEvent

logger = logging.getLogger(__name__)


def build_consumer() -> KafkaConsumer:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.getenv("KAFKA_TOPIC", "model-trained")
    group_id = os.getenv("KAFKA_GROUP_ID", "model-registry")

    return KafkaConsumer(
        topic,
        bootstrap_servers=[s.strip() for s in bootstrap.split(",") if s.strip()],
        group_id=group_id,
        auto_offset_reset=os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
        enable_auto_commit=True,
        max_poll_records=int(os.getenv("KAFKA_MAX_POLL_RECORDS", "1")),
        value_deserializer=lambda v: v.decode("utf-8") if v else "",
    )


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    consumer = build_consumer()
    poll_interval = float(os.getenv("WORKER_POLL_SECONDS", "2"))
    auto_activate = os.getenv("MODEL_REGISTRY_AUTO_ACTIVATE", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    default_status = "active" if auto_activate else "registered"

    logger.info("registry.worker.start topic=%s", os.getenv("KAFKA_TOPIC", "model-trained"))

    while True:
        records = consumer.poll(timeout_ms=int(poll_interval * 1000))
        if not records:
            time.sleep(poll_interval)
            continue

        for _, messages in records.items():
            for msg in messages:
                payload = msg.value
                try:
                    data = json.loads(payload) if payload else {}
                    event = ModelTrainedEvent.model_validate(data)
                except Exception as exc:
                    logger.warning(
                        "registry.worker.invalid_message offset=%s error=%s", msg.offset, exc
                    )
                    continue

                upsert_model(event.model_id, event.model_id)
                upsert_model_version(
                    model_id=event.model_id,
                    version="1.0.0",
                    artifact_uri=event.artifact_uri,
                    metadata_uri=(event.metrics or {}).get("metadata_uri"),
                    metrics=event.metrics,
                    status=default_status,
                )
                logger.info(
                    "registry.worker.upsert model_id=%s artifact_uri=%s",
                    event.model_id,
                    event.artifact_uri,
                )


if __name__ == "__main__":
    run()
