"""Development storage rooted outside the application package."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.storage.base import Storage, StorageError

_FORBIDDEN = set("\\\0:")


class LocalStorage(Storage):
    """Store files under a configured directory using generated keys."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, key: str, data: bytes, content_type: str) -> None:
        del content_type
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.part")
        try:
            temporary.write_bytes(data)
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError("The file could not be stored.") from exc

    def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("The stored file could not be removed.") from exc

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def read(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise StorageError("The stored file could not be read.")
        try:
            return path.read_bytes()
        except OSError as exc:
            raise StorageError("The stored file could not be read.") from exc

    def get_url(self, key: str) -> str:
        self._path(key)
        return key

    def _path(self, key: str) -> Path:
        if (
            not key
            or key.startswith(("/", "\\"))
            or any(character in _FORBIDDEN for character in key)
        ):
            raise StorageError("Invalid storage key.")
        parts = Path(key).parts
        if not parts or ".." in parts or "." in parts:
            raise StorageError("Invalid storage key.")
        root = self.root.resolve()
        path = (root / key).resolve()
        if path != root and root not in path.parents:
            raise StorageError("Invalid storage key.")
        return path
