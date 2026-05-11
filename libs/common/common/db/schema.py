from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

metadata = MetaData()

models = Table(
    "models",
    metadata,
    Column("model_id", Text, primary_key=True),
    Column("name", Text, nullable=True),
    Column("description", Text, nullable=True),
    Column("task", Text, nullable=True),
    Column("owner", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

model_versions = Table(
    "model_versions",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("model_id", Text, ForeignKey("models.model_id", ondelete="CASCADE"), nullable=False),
    Column("version", Text, nullable=False),
    Column("artifact_uri", Text, nullable=True),
    Column("metadata_uri", Text, nullable=True),
    Column("metrics_json", JSONB, nullable=True),
    Column("status", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("model_id", "version", name="uq_model_versions_model_id_version"),
)

experiments = Table(
    "experiments",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("name", Text, nullable=False, unique=True),
    Column("description", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

training_runs = Table(
    "training_runs",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("job_id", Text, nullable=False, unique=True),
    Column("experiment_id", BigInteger, ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True),
    Column("model_id", Text, ForeignKey("models.model_id", ondelete="SET NULL"), nullable=True),
    Column("params_json", JSONB, nullable=True),
    Column("dataset_uri", Text, nullable=True),
    Column("metrics_json", JSONB, nullable=True),
    Column("status", Text, nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

eval_reports = Table(
    "eval_reports",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("model_version_id", BigInteger, ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True),
    Column("report_uri", Text, nullable=True),
    Column("metrics_json", JSONB, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

inference_requests = Table(
    "inference_requests",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("request_id", Text, nullable=False, unique=True),
    Column("model_id", Text, ForeignKey("models.model_id", ondelete="SET NULL"), nullable=True),
    Column("model_version_id", BigInteger, ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True),
    Column("inputs_json", JSONB, nullable=True),
    Column("received_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("latency_ms", Integer, nullable=True),
    Column("status", Text, nullable=True),
    Column("client_id", Text, nullable=True),
    Column("metadata_json", JSONB, nullable=True),
)

inference_results = Table(
    "inference_results",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("request_id", BigInteger, ForeignKey("inference_requests.id", ondelete="CASCADE"), nullable=False),
    Column("output_uri", Text, nullable=True),
    Column("outputs_json", JSONB, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

usage_metrics = Table(
    "usage_metrics",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("service", Text, nullable=False),
    Column("window_start", DateTime(timezone=True), nullable=False),
    Column("window_end", DateTime(timezone=True), nullable=False),
    Column("count", Integer, nullable=True),
    Column("p50_ms", Numeric, nullable=True),
    Column("p95_ms", Numeric, nullable=True),
    Column("error_rate", Numeric, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("service", "window_start", "window_end", name="uq_usage_metrics_service_window"),
)

events = Table(
    "events",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("service", Text, nullable=False),
    Column("event_type", Text, nullable=False),
    Column("payload_json", JSONB, nullable=True),
    Column("correlation_id", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

__all__ = [
    "metadata",
    "models",
    "model_versions",
    "experiments",
    "training_runs",
    "eval_reports",
    "inference_requests",
    "inference_results",
    "usage_metrics",
    "events",
]
