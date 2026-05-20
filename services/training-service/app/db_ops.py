from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from common.db import events, experiments, models, session_scope, training_runs
from contracts.events import TrainingJobEvent


def ensure_experiment(name: str | None) -> int | None:
    if not name:
        return None
    stmt = pg_insert(experiments).values(name=name).on_conflict_do_nothing()
    with session_scope() as session:
        session.execute(stmt)
        return session.execute(select(experiments.c.id).where(experiments.c.name == name)).scalar()


def upsert_model(model_id: str, name: str | None) -> None:
    stmt = (
        pg_insert(models)
        .values(model_id=model_id, name=name)
        .on_conflict_do_update(
            index_elements=[models.c.model_id],
            set_={"name": name, "updated_at": func.now()},
        )
    )
    with session_scope() as session:
        session.execute(stmt)


def record_training_start(
    event: TrainingJobEvent, dataset_uri: str | None, experiment_id: int | None
) -> None:
    params = event.config or {}
    stmt = pg_insert(training_runs).values(
        job_id=event.job_id,
        experiment_id=experiment_id,
        model_id=f"model-{event.job_id}",
        params_json=params,
        dataset_uri=dataset_uri,
        status="running",
        started_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[training_runs.c.job_id],
        set_={
            "experiment_id": experiment_id,
            "model_id": f"model-{event.job_id}",
            "params_json": params,
            "dataset_uri": dataset_uri,
            "status": "running",
            "started_at": datetime.now(UTC),
        },
    )
    with session_scope() as session:
        session.execute(stmt)
        session.execute(
            pg_insert(events).values(
                service="training-service",
                event_type="TRAINING_STARTED",
                payload_json=event.model_dump(),
            )
        )


def reconcile_stale_jobs(timeout_hours: int = 12) -> int:
    """Mark running jobs older than timeout_hours as failed.

    Called at worker startup so pods that crashed mid-training don't leave
    phantom 'running' rows in DB forever. Returns the number of jobs fixed.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=timeout_hours)
    stale_payload = {
        "error": f"stale_running: no completion signal within {timeout_hours}h (pod restart or crash)",
    }
    with session_scope() as session:
        result = session.execute(
            update(training_runs)
            .where(
                training_runs.c.status == "running",
                training_runs.c.started_at < cutoff,
            )
            .values(
                status="failed",
                metrics_json=stale_payload,
                finished_at=datetime.now(UTC),
            )
            .returning(training_runs.c.job_id)
        )
        stale_ids = [row[0] for row in result]
        if stale_ids:
            session.execute(
                pg_insert(events).values(
                    service="training-service",
                    event_type="TRAINING_RECONCILED",
                    payload_json={"stale_job_ids": stale_ids, "timeout_hours": timeout_hours},
                )
            )
    return len(stale_ids)


def record_training_end(
    job_id: str, metrics: dict | None, status: str, error: str | None = None
) -> None:
    payload = {"job_id": job_id, "status": status, "metrics": metrics, "error": error}
    update_values = {
        "status": status,
        "metrics_json": metrics or ({"error": error} if error else None),
        "finished_at": datetime.now(UTC),
    }
    with session_scope() as session:
        session.execute(
            update(training_runs).where(training_runs.c.job_id == job_id).values(**update_values)
        )
        session.execute(
            pg_insert(events).values(
                service="training-service",
                event_type="TRAINING_COMPLETED" if status == "succeeded" else "TRAINING_FAILED",
                payload_json=payload,
            )
        )
