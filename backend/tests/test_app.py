"""Application startup and public API tests."""

import pytest
from fastapi.testclient import TestClient


def test_application_imports_without_connecting() -> None:
    from app.database import session as session_module
    from app.main import app

    assert app.title == "ANDIKA"
    assert session_module._engine is None


def test_root(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "ANDIKA",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


def test_system(client: TestClient) -> None:
    response = client.get("/api/v1/system")

    assert response.status_code == 200
    assert response.json() == {
        "name": "ANDIKA",
        "version": "0.1.0",
        "environment": "test",
        "api_prefix": "/api/v1",
    }


def test_openapi_includes_health(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/health/database" in paths


def test_cors_allows_configured_origin(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})

    assert response.headers.get("access-control-allow-origin") != "https://evil.example"


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found"},
    }


def test_unhandled_errors_hide_internals(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import app

    def explode() -> bool:
        raise RuntimeError("postgresql://andika:secret@db/andika SELECT password")

    monkeypatch.setattr("app.api.v1.endpoints.health.database_is_reachable", explode)
    with TestClient(app, raise_server_exceptions=False) as quiet_client:
        response = quiet_client.get("/api/v1/health/database")

    assert response.status_code == 500
    body = response.text
    assert "secret" not in body
    assert "SELECT" not in body
    assert "Traceback" not in body
    assert response.json()["error"]["code"] == "internal_error"
