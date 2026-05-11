import json
import logging
import os
import threading
import time

from fastapi import FastAPI
from kafka import KafkaConsumer

from app.api.v1 import routes_health, routes_infer
from app.model_store import get_model_entry, pick_default_model
from app.schemas import HealthResponse

app = FastAPI(title="Model Serving", version="0.1.0")

app.include_router(routes_health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(routes_infer.router, prefix="/api/v1/infer", tags=["infer"])


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def _ensure_yolo_config_dir() -> None:
    cfg_dir = os.getenv("YOLO_CONFIG_DIR")
    if not cfg_dir:
        return
    try:
        os.makedirs(cfg_dir, exist_ok=True)
        os.chmod(cfg_dir, 0o777)
        test_path = os.path.join(cfg_dir, ".write_test")
        with open(test_path, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(test_path)
    except Exception:
        logging.getLogger(__name__).warning(
            "model-serving.yolo_config_dir_unwritable path=%s", cfg_dir
        )


def _start_model_listener() -> None:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = os.getenv("MODEL_EVENTS_TOPIC", "model-trained")
    group_id = os.getenv("MODEL_SERVING_GROUP_ID", "model-serving")
    poll_seconds = float(os.getenv("MODEL_SERVING_POLL_SECONDS", "2"))
    auto_warm = os.getenv("MODEL_SERVING_AUTO_WARM", "false").lower() in {"1", "true", "yes"}

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=[s.strip() for s in bootstrap.split(",") if s.strip()],
        group_id=group_id,
        auto_offset_reset=os.getenv("KAFKA_AUTO_OFFSET_RESET", "latest"),
        enable_auto_commit=True,
        max_poll_records=1,
        value_deserializer=lambda v: v.decode("utf-8") if v else "",
    )

    logger = logging.getLogger(__name__)
    logger.info("model-serving.listener.start topic=%s", topic)

    while True:
        records = consumer.poll(timeout_ms=int(poll_seconds * 1000))
        if not records:
            time.sleep(poll_seconds)
            continue
        for _, messages in records.items():
            for msg in messages:
                try:
                    payload = json.loads(msg.value) if msg.value else {}
                except Exception:
                    payload = {}
                model_id = payload.get("model_id")
                entry = get_model_entry(model_id) if model_id else pick_default_model()
                if not entry or not entry.get("artifact_uri"):
                    logger.warning(
                        "model-serving.listener.skip_missing_model model_id=%s", model_id
                    )
                    continue
                logger.info("model-serving.listener.refresh model_id=%s", entry.get("model_id"))
                try:
                    if auto_warm:
                        started = time.time()
                        routes_infer.swap_active_model(entry)
                        elapsed = time.time() - started
                        logger.info(
                            "model-serving.listener.warm_loaded model_id=%s elapsed_sec=%.2f",
                            entry.get("model_id"),
                            elapsed,
                        )
                    else:
                        routes_infer.clear_model_cache()
                except Exception as exc:
                    logger.warning("model-serving.listener.refresh_failed error=%s", exc)


@app.on_event("startup")
def _startup() -> None:
    _ensure_yolo_config_dir()
    if os.getenv("MODEL_SERVING_AUTO_RELOAD", "true").lower() in {"1", "true", "yes"}:
        thread = threading.Thread(target=_start_model_listener, daemon=True)
        thread.start()
