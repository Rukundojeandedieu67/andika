"""Health endpoint tests that do not require PostgreSQL."""

from __future__ import annotations

from typing import Self

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.services.health import database_is_reachable


class _RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: object) -> None:
        self.statements.append(str(statement))

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class _RecordingEngine:
    def __init__(self) -> None:
        self.connection = _RecordingConnection()

    def connect(self) -> _RecordingConnection:
        return self.connection


class _FailingEngine:
    def connect(self) -> None:
        raise SQLAlchemyError("connection to postgresql://andika:secret@db failed")


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "name": "ANDIKA",
        "version": "0.1.0",
    }
    assert response.headers["cache-control"] == "no-store"


def test_database_health_reports_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.v1.endpoints.health.database_is_reachable", lambda: True
    )

    response = client.get("/api/v1/health/database")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_database_health_reports_disconnect(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.v1.endpoints.health.database_is_reachable", lambda: False
    )

    response = client.get("/api/v1/health/database")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "disconnected"}
    assert "secret" not in response.text
    assert "SELECT" not in response.text


def test_database_check_executes_query(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _RecordingEngine()
    monkeypatch.setattr("app.services.health.get_engine", lambda: engine)

    assert database_is_reachable() is True
    assert engine.connection.statements == ["SELECT 1"]


def test_database_check_hides_connection_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.health.get_engine", lambda: _FailingEngine())

    assert database_is_reachable() is False
