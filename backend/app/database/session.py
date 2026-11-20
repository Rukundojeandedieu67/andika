"""Database engine and request-scoped sessions.

The engine is created on first use so importing the application does not open
a PostgreSQL connection. Schema changes belong in Alembic, not startup.
"""

from __future__ import annotations

import threading
from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_engine_lock = threading.Lock()


def _create_engine() -> Engine:
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        return create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.debug,
        )
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={"connect_timeout": 3},
        echo=settings.debug,
    )


def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, creating it once."""

    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is None:
            _engine = _create_engine()
    if _engine is None:
        raise RuntimeError("Database engine was not created.")
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the session factory bound to the application engine."""

    global _session_factory
    if _session_factory is not None:
        return _session_factory
    engine = get_engine()
    with _engine_lock:
        if _session_factory is None:
            _session_factory = sessionmaker(
                bind=engine,
                autoflush=False,
                expire_on_commit=False,
            )
    if _session_factory is None:
        raise RuntimeError("Database session factory was not created.")
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """Yield a session, commit on success, and always close it."""

    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    """Close pooled connections. Safe to call when no engine exists."""

    global _engine, _session_factory
    with _engine_lock:
        engine = _engine
        _engine = None
        _session_factory = None
    if engine is not None:
        engine.dispose()
