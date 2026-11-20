"""Pytest fixtures and isolated test configuration."""

from __future__ import annotations

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "false"
os.environ["APP_NAME"] = "ANDIKA"
os.environ["APP_VERSION"] = "0.1.0"
os.environ["API_V1_PREFIX"] = "/api/v1"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-only-jwt-secret-key-with-32-characters"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["AUTH_RATE_LIMIT_ENABLED"] = "false"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import reset_rate_limiters
from app.database.session import dispose_engine

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_runtime_state() -> Iterator[None]:
    """Drop cached settings and engines so tests stay isolated."""

    get_settings.cache_clear()
    dispose_engine()
    reset_rate_limiters()
    yield
    get_settings.cache_clear()
    dispose_engine()
    reset_rate_limiters()


@pytest.fixture
def client() -> Iterator[TestClient]:
    import app.models
    from app.database.base import Base
    from app.database.session import get_engine
    from app.main import app
    from app.services.email_service import get_email_service
    from tests.mail import RecordingEmailService

    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    mailbox = RecordingEmailService(get_settings())
    app.dependency_overrides[get_email_service] = lambda: mailbox
    with TestClient(app) as test_client:
        test_client.mailbox = mailbox  # type: ignore[attr-defined]
        yield test_client
    app.dependency_overrides.clear()
