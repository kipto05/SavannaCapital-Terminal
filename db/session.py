"""
db/session.py — SQLAlchemy engine, session factory, and FastAPI dependency.
Swap DATABASE_URL to switch between SQLite (dev) and PostgreSQL (prod).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from config.settings import config

log = logging.getLogger(__name__)

Base = declarative_base()

engine = create_engine(
    config.db.url,
    pool_size=config.db.pool_size,
    max_overflow=config.db.max_overflow,
    pool_timeout=config.db.pool_timeout,
    echo=config.db.echo_sql,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)


def get_db() -> Generator:
    """
    FastAPI dependency. Yields a per-request session and closes it on return.
    Usage:
        from fastapi import Depends
        from db.session import get_db
        from sqlalchemy.orm import Session

        @router.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Context manager for scripts and background tasks that need a manual session.
    Commits on success, rolls back on exception, always closes.
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
