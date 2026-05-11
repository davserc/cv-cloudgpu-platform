"""initial_schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-01 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "models",
        sa.Column("model_id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("task", sa.Text, nullable=True),
        sa.Column("owner", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "model_versions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("model_id", sa.Text, sa.ForeignKey("models.model_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Text, nullable=False),
        sa.Column("artifact_uri", sa.Text, nullable=True),
        sa.Column("metadata_uri", sa.Text, nullable=True),
        sa.Column("metrics_json", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("model_id", "version", name="uq_model_versions_model_id_version"),
    )
    op.create_index("ix_model_versions_model_id", "model_versions", ["model_id"])

    op.create_table(
        "experiments",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "training_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Text, nullable=False, unique=True),
        sa.Column("experiment_id", sa.BigInteger, sa.ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("model_id", sa.Text, sa.ForeignKey("models.model_id", ondelete="SET NULL"), nullable=True),
        sa.Column("params_json", postgresql.JSONB, nullable=True),
        sa.Column("dataset_uri", sa.Text, nullable=True),
        sa.Column("metrics_json", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_training_runs_job_id", "training_runs", ["job_id"])
    op.create_index("ix_training_runs_model_id", "training_runs", ["model_id"])

    op.create_table(
        "eval_reports",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("model_version_id", sa.BigInteger, sa.ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("report_uri", sa.Text, nullable=True),
        sa.Column("metrics_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eval_reports_model_version_id", "eval_reports", ["model_version_id"])

    op.create_table(
        "inference_requests",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.Text, nullable=False, unique=True),
        sa.Column("model_id", sa.Text, sa.ForeignKey("models.model_id", ondelete="SET NULL"), nullable=True),
        sa.Column("model_version_id", sa.BigInteger, sa.ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("client_id", sa.Text, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_inference_requests_request_id", "inference_requests", ["request_id"])
    op.create_index("ix_inference_requests_model_id", "inference_requests", ["model_id"])

    op.create_table(
        "inference_results",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.BigInteger, sa.ForeignKey("inference_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("output_uri", sa.Text, nullable=True),
        sa.Column("outputs_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_inference_results_request_id", "inference_results", ["request_id"])

    op.create_table(
        "usage_metrics",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("service", sa.Text, nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer, nullable=True),
        sa.Column("p50_ms", sa.Numeric, nullable=True),
        sa.Column("p95_ms", sa.Numeric, nullable=True),
        sa.Column("error_rate", sa.Numeric, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("service", "window_start", "window_end", name="uq_usage_metrics_service_window"),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("service", sa.Text, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("payload_json", postgresql.JSONB, nullable=True),
        sa.Column("correlation_id", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_events_service", "events", ["service"])
    op.create_index("ix_events_event_type", "events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_index("ix_events_service", table_name="events")
    op.drop_table("events")

    op.drop_table("usage_metrics")

    op.drop_index("ix_inference_results_request_id", table_name="inference_results")
    op.drop_table("inference_results")

    op.drop_index("ix_inference_requests_model_id", table_name="inference_requests")
    op.drop_index("ix_inference_requests_request_id", table_name="inference_requests")
    op.drop_table("inference_requests")

    op.drop_index("ix_eval_reports_model_version_id", table_name="eval_reports")
    op.drop_table("eval_reports")

    op.drop_index("ix_training_runs_model_id", table_name="training_runs")
    op.drop_index("ix_training_runs_job_id", table_name="training_runs")
    op.drop_table("training_runs")

    op.drop_table("experiments")

    op.drop_index("ix_model_versions_model_id", table_name="model_versions")
    op.drop_table("model_versions")

    op.drop_table("models")
