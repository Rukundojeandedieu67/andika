"""Direct messages between two signed-in accounts."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.core.dependencies import CurrentUser, DatabaseSession
from app.schemas.chat import (
    ConversationOpen,
    ConversationRead,
    MessageCreate,
    MessagePage,
    MessageRead,
)
from app.schemas.common import ErrorResponse
from app.services import chat_service
from app.services.exceptions import ServiceError

router = APIRouter()

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[ConversationRead], summary="List your conversations", responses=_ERRORS)
def list_conversations(actor: CurrentUser, session: DatabaseSession) -> list[ConversationRead]:
    return chat_service.list_conversations(session, actor)


@router.post("", response_model=ConversationRead, summary="Open a conversation", responses=_ERRORS)
def open_conversation(
    payload: ConversationOpen, actor: CurrentUser, session: DatabaseSession
) -> ConversationRead:
    try:
        return chat_service.open_conversation(session, actor, payload.username)
    except ServiceError as exc:
        _raise(exc)


@router.get(
    "/{conversation_id}/messages",
    response_model=MessagePage,
    summary="Read messages in a conversation",
    responses=_ERRORS,
)
def list_messages(
    conversation_id: UUID,
    actor: CurrentUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessagePage:
    try:
        return chat_service.list_messages(
            session, actor, conversation_id, page=page, page_size=page_size
        )
    except ServiceError as exc:
        _raise(exc)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageRead,
    summary="Send a message",
    responses=_ERRORS,
)
def send_message(
    conversation_id: UUID,
    payload: MessageCreate,
    actor: CurrentUser,
    session: DatabaseSession,
) -> MessageRead:
    try:
        return chat_service.send_message(session, actor, conversation_id, payload.body)
    except ServiceError as exc:
        _raise(exc)
