"""Health-check response models."""

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    name: str
    version: str


class DatabaseHealth(BaseModel):
    status: str
    database: str
