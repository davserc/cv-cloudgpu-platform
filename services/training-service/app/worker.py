import json
import logging
import os
import queue
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Semaphore
from uuid import uuid4

from kafka import KafkaConsumer, KafkaProducer
from kafka.structs import OffsetAndMetadata, TopicPartition
from sqlalchemy.dialects.postgresql import insert as pg_insert

from common.db import events, session_scope
from contracts.events import ModelTrainedEvent, TrainingJobEvent

from .db_ops import ensure_experiment, record_training_end, record_training_start, upsert_model
from .gcs_utils import upload_artifact_to_gcs
from .metrics import parse_ultralytics_metrics
from .training import build_run_cmd, model_base_name, resolve_artifact_src
from .vast_runner import train_on_instance

logger = logging.getLogger(__name__)


def build_consumer() -> KafkaConsumer:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.getenv("KAFKA_TOPIC", "training-jobs")
    group_id = os.getenv("KAFKA_GROUP_ID", "training-service")
    max_poll_interval_ms = int(os.getenv("KAFKA_MAX_POLL_INTERVAL_MS", "7200000"))
    max_poll_records = int(os.getenv("KAFKA_MAX_POLL_RECORDS", "1"))

    return KafkaConsumer(
        topic,
        bootstrap_servers=[s.strip() for s in bootstrap.split(",") if s.strip()],
        group_id=group_id,
        auto_offset_reset=os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
        enable_auto_commit=False,
        max_poll_interval_ms=max_poll_interval_ms,
        max_poll_records=max_poll_records,
        value_deserializer=lambda v: v.decode("utf-8") if v else "",
    )


def build_producer() -> KafkaProducer:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    return KafkaProducer(
        bootstrap_servers=[s.strip() for s in bootstrap.split(",") if s.strip()],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def _env_float(name: str) -> float | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        logger.warning("worker.invalid_env_float name=%s value=%s", name, value)
        return None


def _cfg(event: TrainingJobEvent, key: str, env_key: str, default=None):
    if event.config and isinstance(event.config, dict):
        val = event.config.get(key)
        if val is not None:
            return val
    env_val = os.getenv(env_key)
    return env_val if env_val is not None else default


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    consumer = build_consumer()
    producer = build_producer()
    output_topic = os.getenv("KAFKA_OUTPUT_TOPIC", "model-trained")
    dlq_topic = os.getenv("KAFKA_DLQ_TOPIC", "training-jobs-dlq")
    poll_interval = float(os.getenv("WORKER_POLL_SECONDS", "2"))
    max_workers = int(os.getenv("WORKER_MAX_CONCURRENCY", "2"))
    if max_workers < 1:
        max_workers = 1
    slots = Semaphore(max_workers)
    executor = ThreadPoolExecutor(max_workers=max_workers)
    commit_queue_max = int(os.getenv("KAFKA_COMMIT_QUEUE_MAX", "1000"))
    commit_queue: queue.Queue[tuple[str, int, int]] = queue.Queue(maxsize=commit_queue_max)
    pending_offsets: dict[TopicPartition, set[int]] = {}
    last_committed: dict[TopicPartition, int] = {}

    def enqueue_commit(topic: str, partition: int, offset: int) -> None:
        try:
            commit_queue.put_nowait((topic, partition, offset))
        except queue.Full:
            logger.warning(
                "worker.commit_queue_full topic=%s partition=%s offset=%s",
                topic,
                partition,
                offset,
            )
            try:
                commit_queue.put((topic, partition, offset), timeout=5)
            except queue.Full:
                logger.error(
                    "worker.commit_queue_drop topic=%s partition=%s offset=%s",
                    topic,
                    partition,
                    offset,
                )

    def make_offset_metadata(next_offset: int) -> OffsetAndMetadata:
        try:
            return OffsetAndMetadata(next_offset, None)
        except TypeError:
            return OffsetAndMetadata(next_offset, None, -1)

    def publish_failed(event: TrainingJobEvent, error: str, topic: str, partition: int, offset: int) -> None:
        failed_event = {
            "event_type": "training-failed",
            "event_id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "job_id": event.job_id,
            "error": error,
            "config": event.config,
        }
        try:
            producer.send(dlq_topic, failed_event)
            producer.flush()
            logger.info(
                "worker.dlq_published event=%s job_id=%s topic=%s",
                failed_event["event_type"],
                event.job_id,
                dlq_topic,
            )
        except Exception as publish_exc:
            logger.error(
                "worker.dlq_failed job_id=%s error=%s",
                event.job_id,
                publish_exc,
            )
        enqueue_commit(topic, partition, offset)

    def handle_shutdown(signum, frame) -> None:
        logger.info("worker.shutdown signal=%s", signum)
        try:
            consumer.close()
            producer.flush(5)
            producer.close()
        finally:
            executor.shutdown(wait=True)
            sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info("worker.start topic=%s output_topic=%s", os.getenv("KAFKA_TOPIC", "training-jobs"), output_topic)

    def process_event(event: TrainingJobEvent, topic: str, partition: int, offset: int) -> None:
        try:
            logger.info("worker.message offset=%s job_id=%s", offset, event.job_id)

            dataset_url = _cfg(event, "train_dataset_url", "TRAIN_DATASET_URL") or _cfg(event, "dataset_url", "TRAIN_DATASET_URL")
            dataset_gs_uri = _cfg(event, "dataset_gs_uri", "TRAIN_DATASET_GS_URI")
            dataset_uri = dataset_url or dataset_gs_uri

            project = _cfg(event, "project", "TRAIN_PROJECT", "runs")
            model = _cfg(event, "model", "TRAIN_MODEL", "yolo11s.pt")
            name = _cfg(event, "name", "TRAIN_NAME", event.job_id)

            experiment_id = ensure_experiment(project)
            upsert_model(f"model-{event.job_id}", name or model_base_name(str(model)))
            record_training_start(event, dataset_uri, experiment_id)

            if not dataset_url and not dataset_gs_uri:
                logger.warning("worker.missing_dataset_url job_id=%s", event.job_id)
                record_training_end(event.job_id, None, "failed", "missing_dataset_url")
                publish_failed(event, "missing_dataset_url", topic, partition, offset)
                return

            dataset_dst = os.getenv("TRAIN_DATASET_DST", "/work/datasets")
            image = os.getenv("TRAIN_IMAGE", "pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime")
            ports = os.getenv("TRAIN_PORTS")
            artifact_src = resolve_artifact_src(event)
            artifact_dir = Path(os.getenv("TRAIN_ARTIFACT_DST", "./storage/artifacts"))
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact_dst = artifact_dir / f"best_{event.job_id}.pt"
            log_path = os.getenv("TRAIN_LOG_PATH")
            if not log_path:
                log_dir = Path(os.getenv("TRAIN_LOG_DIR", "./storage/artifacts"))
                log_dir.mkdir(parents=True, exist_ok=True)
                log_path = str(log_dir / f"train_{event.job_id}.log")
            run_cmd = build_run_cmd(event)

            try:
                dataset_label = dataset_url or dataset_gs_uri or "unknown"
                logger.info(
                    "worker.dataset_prepare_start job_id=%s src=remote:%s dst=%s",
                    event.job_id,
                    dataset_label,
                    dataset_dst,
                )
                gcp_sa_b64 = _cfg(event, "gcp_sa_b64", "GCP_SA_B64")
                logger.info(
                    "gcp_sa_b64_len env=%s param=%s",
                    len(os.getenv("GCP_SA_B64") or ""),
                    len(gcp_sa_b64 or ""),
                )

                dataset_archive_name = _cfg(event, "dataset_archive_name", "TRAIN_DATASET_ARCHIVE_NAME")
                extract_cmd = _cfg(event, "extract_cmd", "TRAIN_EXTRACT_CMD")

                install_gsutil_raw = _cfg(event, "install_gsutil", "TRAIN_INSTALL_GSUTIL", "false")
                install_gsutil = str(install_gsutil_raw).lower() in ("1", "true", "yes", "on")

                train_dataset_url = dataset_url or dataset_gs_uri
                train_on_instance(
                    api_key=os.getenv("VAST_API_KEY"),
                    image=image,
                    ports=ports,
                    dataset_dst=dataset_dst,
                    run_cmd=run_cmd,
                    artifact_src=artifact_src,
                    artifact_dst=artifact_dst,
                    log_path=log_path,
                    max_price=_env_float("VAST_MAX_PRICE"),
                    min_cuda=_env_float("VAST_MIN_CUDA"),
                    max_cuda=_env_float("VAST_MAX_CUDA"),
                    gcp_sa_b64=gcp_sa_b64,
                    dataset_gs_uri=dataset_gs_uri,
                    dataset_archive_name=dataset_archive_name,
                    extract_cmd=extract_cmd,
                    install_gsutil=install_gsutil,
                    train_dataset_url=train_dataset_url,
                    ssh_timeout_sec=int(os.getenv("TRAIN_SSH_TIMEOUT_SEC", "900")),
                    ssh_poll_interval_sec=int(os.getenv("TRAIN_SSH_POLL_INTERVAL_SEC", "10")),
                    cmd_retries=int(os.getenv("TRAIN_CMD_RETRIES", "10")),
                    cmd_backoff_sec=float(os.getenv("TRAIN_CMD_BACKOFF_SEC", "10")),
                )
                logger.info(
                    "worker.train_complete job_id=%s artifact=%s log=%s",
                    event.job_id,
                    artifact_dst,
                    log_path,
                )

                artifact_uri = str(artifact_dst)
                metadata_uri = None
                model_base = model_base_name(str(model))
                base_uri = os.getenv("TRAIN_MODEL_GCS_BASE_URI")
                if base_uri:
                    try:
                        metadata = {
                            "model_id": f"model-{event.job_id}",
                            "job_id": event.job_id,
                            "name": model_base,
                            "version": "1.0.0",
                            "artifact_uri": artifact_uri,
                            "trained_at": datetime.now(UTC).isoformat(),
                        }
                        artifact_uri, metadata_uri = upload_artifact_to_gcs(
                            artifact_path=artifact_dst,
                            base_uri=base_uri,
                            model_base=model_base,
                            job_id=event.job_id,
                            metadata=metadata,
                            gcp_sa_b64=gcp_sa_b64,
                        )
                        logger.info(
                            "worker.model_uploaded job_id=%s artifact_uri=%s metadata_uri=%s",
                            event.job_id,
                            artifact_uri,
                            metadata_uri,
                        )
                    except Exception as exc:
                        logger.error("worker.model_upload_failed job_id=%s error=%s", event.job_id, exc)

            except Exception as exc:
                logger.error("worker.train_failed job_id=%s error=%s", event.job_id, exc)
                record_training_end(event.job_id, None, "failed", str(exc))
                publish_failed(event, str(exc), topic, partition, offset)
                return

            metrics = parse_ultralytics_metrics(log_path) or {"mAP": 0.0}
            if metadata_uri:
                metrics["metadata_uri"] = metadata_uri
            record_training_end(event.job_id, metrics, "succeeded")

            trained_event = ModelTrainedEvent(
                event_id=str(uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                job_id=event.job_id,
                model_id=f"model-{event.job_id}",
                artifact_uri=artifact_uri,
                metrics=metrics,
            )

            with session_scope() as session:
                session.execute(
                    pg_insert(events).values(
                        service="training-service",
                        event_type=trained_event.event_type,
                        payload_json=trained_event.model_dump(),
                    )
                )

            producer.send(output_topic, trained_event.model_dump())
            producer.flush()
            logger.info("worker.published event=%s model_id=%s", trained_event.event_type, trained_event.model_id)
            enqueue_commit(topic, partition, offset)
        finally:
            slots.release()

    while True:
        pending: list[tuple[str, int, int]] = []
        while True:
            try:
                pending.append(commit_queue.get_nowait())
            except queue.Empty:
                break
        if pending:
            for topic, partition, offset in pending:
                tp = TopicPartition(topic, partition)
                pending_offsets.setdefault(tp, set()).add(offset)

            offsets: dict[TopicPartition, OffsetAndMetadata] = {}
            for tp, offsets_set in list(pending_offsets.items()):
                if tp not in last_committed:
                    committed = consumer.committed(tp)
                    last_committed[tp] = (committed - 1) if committed is not None else -1
                current = last_committed[tp]
                next_offset = current + 1
                advanced = False
                while next_offset in offsets_set:
                    offsets_set.remove(next_offset)
                    current = next_offset
                    next_offset += 1
                    advanced = True
                if advanced:
                    last_committed[tp] = current
                    offsets[tp] = make_offset_metadata(current + 1)
                if not offsets_set:
                    pending_offsets.pop(tp, None)

            if offsets:
                consumer.commit(offsets=offsets)

        records = consumer.poll(timeout_ms=int(poll_interval * 1000))
        if not records:
            time.sleep(poll_interval)
            continue

        for _, messages in records.items():
            for msg in messages:
                payload = msg.value
                try:
                    data = json.loads(payload) if payload else {}
                    event = TrainingJobEvent.model_validate(data)
                except Exception as exc:
                    logger.warning("worker.invalid_message offset=%s error=%s", msg.offset, exc)
                    continue

                slots.acquire()
                try:
                    executor.submit(process_event, event, msg.topic, msg.partition, msg.offset)
                except Exception:
                    slots.release()
                    raise


if __name__ == "__main__":
    run()
