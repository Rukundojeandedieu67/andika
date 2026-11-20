"""Connectivity checks used by health endpoints."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database.session import get_engine

logger = logging.getLogger(__name__)


def database_is_reachable() -> bool:
    """Return whether PostgreSQL accepts a connection and a trivial query."""

    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        logger.warning("Database connectivity check failed: %s", type(exc).__name__)
        return False
