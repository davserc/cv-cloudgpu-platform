from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from common.db.engine import build_engine


SessionLocal = sessionmaker(bind=build_engine(), autocommit=False, autoflush=False)


@contextmanager
def session_scope() -> Session:
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
