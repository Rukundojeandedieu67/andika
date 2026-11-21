"""Storage operations shared by local and object-storage adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageError(Exception):
    """A storage operation failed. The message is safe to log and return."""

    def __init__(self, message: str = "Storage request failed.") -> None:
        self.message = message
        super().__init__(message)


class Storage(ABC):
    """Provider-neutral file storage."""

    @abstractmethod
    def save(self, key: str, data: bytes, content_type: str) -> None:
        """Store bytes at a generated key."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove an object. Missing objects are not an error."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return whether the key is stored."""

    @abstractmethod
    def read(self, key: str) -> bytes:
        """Return the stored bytes."""

    @abstractmethod
    def get_url(self, key: str) -> str:
        """Return a delivery URL. Local adapters return the key, not a filesystem path."""
