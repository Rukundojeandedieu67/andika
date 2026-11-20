"""Shared API response models."""

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ValidationErrorItem(BaseModel):
    loc: list[str | int]
    message: str


class ValidationErrorResponse(BaseModel):
    error: ErrorDetail
    details: list[ValidationErrorItem] = Field(default_factory=list)


class RootResponse(BaseModel):
    name: str
    version: str
    docs: str
    health: str
