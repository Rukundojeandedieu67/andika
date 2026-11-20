"""Configuration validation tests."""

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_DATABASE_URL, Settings


def test_development_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "APP_NAME",
        "APP_VERSION",
        "API_V1_PREFIX",
        "ENVIRONMENT",
        "DEBUG",
        "DATABASE_URL",
        "JWT_SECRET_KEY",
        "JWT_ALGORITHM",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "AUTH_RATE_LIMIT_ENABLED",
        "PUBLIC_APP_URL",
        "SMTP_HOST",
        "SMTP_FROM_EMAIL",
        "CORS_ORIGINS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_name == "ANDIKA"
    assert settings.environment == "development"
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_expire_minutes == 15
    assert settings.auth_rate_limit_enabled is True
    assert settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_postgres_url_is_normalized_to_psycopg() -> None:
    settings = Settings(
        database_url="postgresql://andika:andika@localhost:5432/andika",
    )

    assert settings.database_url == (
        "postgresql+psycopg://andika:andika@localhost:5432/andika"
    )


def test_cors_accepts_comma_separated_and_json_values() -> None:
    csv_settings = Settings(cors_origins="http://localhost:5173, http://127.0.0.1:5173")
    json_settings = Settings(cors_origins='["https://andika.example"]')

    assert csv_settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    assert json_settings.cors_origins == ["https://andika.example"]


def test_invalid_database_url_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="development", database_url="sqlite:///andika.db")


@pytest.mark.parametrize(
    "overrides",
    [
        {"jwt_secret_key": "short"},
        {"jwt_secret_key": "change-me-but-long-enough-to-pass-length"},
        {"debug": True},
        {"cors_origins": ["*"]},
        {"cors_origins": []},
        {"database_url": DEFAULT_DATABASE_URL},
        {
            "database_url": (
                "postgresql+psycopg://andika_app:password@db.internal:5432/andika"
            )
        },
    ],
)
def test_production_rejects_unsafe_configuration(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "environment": "production",
        "debug": False,
        "jwt_secret_key": "a" * 48,
        "database_url": "postgresql+psycopg://andika_app:s3cure-pass@db.internal:5432/andika",
        "cors_origins": ["https://andika.example"],
    }
    values.update(overrides)

    with pytest.raises(ValidationError):
        Settings(**values)  # type: ignore[arg-type]


def test_production_accepts_explicit_configuration() -> None:
    settings = Settings(
        environment="production",
        debug=False,
        jwt_secret_key="a" * 48,
        database_url="postgresql+psycopg://andika_app:s3cure-pass@db.internal:5432/andika",
        cors_origins=["https://andika.example"],
    )

    assert settings.is_production is True
    assert settings.database_url.startswith("postgresql+psycopg://")
