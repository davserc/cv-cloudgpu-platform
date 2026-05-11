from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from common.db import model_versions, models, session_scope


def upsert_model(model_id: str, name: str | None = None) -> None:
    stmt = pg_insert(models).values(
        model_id=model_id,
        name=name,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[models.c.model_id],
        set_={
            "name": stmt.excluded.name,
            "updated_at": func.now(),
        },
    )
    with session_scope() as session:
        session.execute(stmt)


def upsert_model_version(
    *,
    model_id: str,
    version: str,
    artifact_uri: str | None,
    metadata_uri: str | None,
    metrics: dict | None,
    status: str | None,
) -> None:
    stmt = pg_insert(model_versions).values(
        model_id=model_id,
        version=version,
        artifact_uri=artifact_uri,
        metadata_uri=metadata_uri,
        metrics_json=metrics,
        status=status,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[model_versions.c.model_id, model_versions.c.version],
        set_={
            "artifact_uri": stmt.excluded.artifact_uri,
            "metadata_uri": stmt.excluded.metadata_uri,
            "metrics_json": stmt.excluded.metrics_json,
            "status": stmt.excluded.status,
            "updated_at": func.now(),
        },
    )
    with session_scope() as session:
        session.execute(stmt)


def list_latest_models() -> list[dict[str, Any]]:
    latest = (
        select(
            model_versions.c.model_id,
            model_versions.c.version,
            model_versions.c.artifact_uri,
            model_versions.c.metadata_uri,
            model_versions.c.metrics_json.label("metrics"),
            model_versions.c.status,
            model_versions.c.created_at,
            model_versions.c.updated_at,
            models.c.name,
        )
        .select_from(model_versions.join(models, model_versions.c.model_id == models.c.model_id))
        .distinct(model_versions.c.model_id)
        .order_by(model_versions.c.model_id, model_versions.c.updated_at.desc())
    )
    with session_scope() as session:
        rows = session.execute(latest).mappings().all()
    return [dict(row) for row in rows]


def get_latest_model(model_id: str) -> dict[str, Any] | None:
    stmt = (
        select(
            model_versions.c.model_id,
            model_versions.c.version,
            model_versions.c.artifact_uri,
            model_versions.c.metadata_uri,
            model_versions.c.metrics_json.label("metrics"),
            model_versions.c.status,
            model_versions.c.created_at,
            model_versions.c.updated_at,
            models.c.name,
        )
        .select_from(model_versions.join(models, model_versions.c.model_id == models.c.model_id))
        .where(model_versions.c.model_id == model_id)
        .order_by(model_versions.c.updated_at.desc())
        .limit(1)
    )
    with session_scope() as session:
        row = session.execute(stmt).mappings().first()
    return dict(row) if row else None


def update_latest_model(
    model_id: str,
    status: str | None,
    metadata_uri: str | None,
    metrics: dict | None,
) -> dict[str, Any] | None:
    latest_id_stmt = (
        select(model_versions.c.id)
        .where(model_versions.c.model_id == model_id)
        .order_by(model_versions.c.updated_at.desc())
        .limit(1)
    )
    with session_scope() as session:
        latest_id = session.execute(latest_id_stmt).scalar()
        if latest_id is None:
            return None
        update_values: dict[str, Any] = {"updated_at": func.now()}
        if status is not None:
            update_values["status"] = status
        if metadata_uri is not None:
            update_values["metadata_uri"] = metadata_uri
        if metrics is not None:
            existing = session.execute(
                select(model_versions.c.metrics_json).where(model_versions.c.id == latest_id)
            ).scalar()
            merged = dict(existing or {})
            merged.update(metrics)
            update_values["metrics_json"] = merged
        session.execute(
            update(model_versions).where(model_versions.c.id == latest_id).values(**update_values)
        )

    return get_latest_model(model_id)


def delete_model(model_id: str) -> bool:
    with session_scope() as session:
        result = session.execute(delete(models).where(models.c.model_id == model_id))
        return (result.rowcount or 0) > 0
