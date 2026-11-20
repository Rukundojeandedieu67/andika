"""Database session tests that do not open a PostgreSQL connection."""

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.database.session import dispose_engine, get_db, get_engine, get_session_factory


class _FakeSession:
    def __init__(self, *, fail_commit: bool = False) -> None:
        self.fail_commit = fail_commit
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        if self.fail_commit:
            raise SQLAlchemyError("commit failed")
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_get_db_commits_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(
        "app.database.session.get_session_factory",
        lambda: lambda: session,
    )

    generator = get_db()
    assert next(generator) is session
    with pytest.raises(StopIteration):
        next(generator)

    assert session.committed is True
    assert session.rolled_back is False
    assert session.closed is True


def test_get_db_rolls_back_and_closes_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(
        "app.database.session.get_session_factory",
        lambda: lambda: session,
    )

    generator = get_db()
    next(generator)
    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("request failed"))

    assert session.committed is False
    assert session.rolled_back is True
    assert session.closed is True


def test_session_factory_is_created_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: dict[str, object] = {}

    class _DisposableEngine:
        def dispose(self) -> None:
            return None

    def fake_create_engine(*_args: object, **_kwargs: object) -> _DisposableEngine:
        engine = _DisposableEngine()
        created["engine"] = engine
        return engine

    monkeypatch.setattr("app.database.session.create_engine", fake_create_engine)
    dispose_engine()

    factory = get_session_factory()
    session = factory()
    session.close()

    assert get_engine() is created["engine"]
    assert factory.kw["bind"] is created["engine"]
