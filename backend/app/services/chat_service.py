"""Direct messages. A thread exists only between two active accounts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, Conversation
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.chat import ConversationRead, MessagePage, MessageRead
from app.schemas.post import AuthorPublic
from app.services.exceptions import NotFoundError, ServiceError

_NOT_FOUND = "Conversation not found."
_MAX_BODY = 2000


def list_conversations(session: Session, actor: User) -> list[ConversationRead]:
    rows = session.scalars(
        select(Conversation)
        .where(_member(actor.id))
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
    ).all()
    if not rows:
        return []
    ids = [row.id for row in rows]
    latest = _latest_messages(session, ids)
    people = _users(session, _other_ids(rows, actor.id))
    return [
        ConversationRead(
            id=row.id,
            other=_public(people[other_id]),
            last_message=latest.get(row.id, (None, None))[0],
            last_message_at=latest.get(row.id, (None, None))[1],
            updated_at=row.updated_at,
        )
        for row in rows
        if (other_id := _other(row, actor.id)) in people
    ]


def open_conversation(session: Session, actor: User, username: str) -> ConversationRead:
    other = UserRepository(session).get_by_username_key(username.strip())
    if other is None or not other.is_active:
        raise NotFoundError("No active account uses that username.")
    if other.id == actor.id:
        raise ServiceError("You cannot start a chat with yourself.", 422)
    low, high = _pair(actor.id, other.id)
    conversation = session.scalar(
        select(Conversation).where(
            Conversation.user_low_id == low,
            Conversation.user_high_id == high,
        )
    )
    if conversation is None:
        conversation = Conversation(user_low_id=low, user_high_id=high)
        session.add(conversation)
        session.flush()
    latest = _latest_messages(session, [conversation.id])
    body, when = latest.get(conversation.id, (None, None))
    return ConversationRead(
        id=conversation.id,
        other=_public(other),
        last_message=body,
        last_message_at=when,
        updated_at=conversation.updated_at,
    )


def list_messages(
    session: Session, actor: User, conversation_id: uuid.UUID, *, page: int, page_size: int
) -> MessagePage:
    conversation = _require_member(session, actor, conversation_id)
    total = int(
        session.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.conversation_id == conversation.id)
        )
        or 0
    )
    rows = session.scalars(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    rows.reverse()
    senders = _users(session, {row.sender_id for row in rows})
    return MessagePage(
        items=[
            MessageRead(
                id=row.id,
                conversation_id=row.conversation_id,
                body=row.body,
                created_at=row.created_at,
                sender=_public(senders[row.sender_id]),
                mine=row.sender_id == actor.id,
            )
            for row in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


def send_message(
    session: Session, actor: User, conversation_id: uuid.UUID, body: str
) -> MessageRead:
    conversation = _require_member(session, actor, conversation_id)
    text = " ".join(body.split())
    if text == "" or len(text) > _MAX_BODY:
        raise ServiceError("A message must be between 1 and 2000 characters.", 422)
    now = datetime.now(UTC)
    message = ChatMessage(
        conversation_id=conversation.id, sender_id=actor.id, body=text, created_at=now
    )
    conversation.updated_at = now
    session.add(message)
    session.flush()
    return MessageRead(
        id=message.id,
        conversation_id=message.conversation_id,
        body=message.body,
        created_at=message.created_at,
        sender=_public(actor),
        mine=True,
    )


def _require_member(session: Session, actor: User, conversation_id: uuid.UUID) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or actor.id not in {conversation.user_low_id, conversation.user_high_id}:
        raise NotFoundError(_NOT_FOUND)
    return conversation


def _member(user_id: uuid.UUID):
    return or_(Conversation.user_low_id == user_id, Conversation.user_high_id == user_id)


def _pair(left: uuid.UUID, right: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (left, right) if left.int < right.int else (right, left)


def _other(conversation: Conversation, actor_id: uuid.UUID) -> uuid.UUID:
    if conversation.user_low_id == actor_id:
        return conversation.user_high_id
    return conversation.user_low_id


def _other_ids(rows: list[Conversation], actor_id: uuid.UUID) -> set[uuid.UUID]:
    return {_other(row, actor_id) for row in rows}


def _users(session: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    people = session.scalars(select(User).where(User.id.in_(ids))).all()
    return {person.id: person for person in people}


def _latest_messages(
    session: Session, conversation_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, object]]:
    if not conversation_ids:
        return {}
    rows = session.execute(
        select(ChatMessage.conversation_id, ChatMessage.body, ChatMessage.created_at)
        .where(ChatMessage.conversation_id.in_(conversation_ids))
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
    ).all()
    found: dict[uuid.UUID, tuple[str, object]] = {}
    for conversation_id, body, created_at in rows:
        found.setdefault(conversation_id, (body, created_at))
    return found


def _public(user: User) -> AuthorPublic:
    return AuthorPublic(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
    )
