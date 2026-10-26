"""Invitations and messaging."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from .common import RoleText, Strict

Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class InviteIn(Strict):
    candidate_id: str = Field(min_length=1, max_length=64)
    role: RoleText | None = None
    message: Note = ""


class InviteByHandleIn(Strict):
    handle: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=24)]
    role: RoleText | None = None
    message: Note = ""


class JoinRequestIn(Strict):
    role: RoleText | None = None
    message: Note = ""


class InvitationOut(BaseModel):
    id: str
    project_id: str
    project_title: str
    kind: Literal["invite", "request"]
    from_user: dict
    candidate: dict
    role: str | None
    message: str
    status: str
    reason: str | None = None
    created_at: datetime
    responded_at: datetime | None = None


class StartConversationIn(Strict):
    user_id: str = Field(min_length=1, max_length=64)


class SendMessageIn(Strict):
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    client_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{8,64}$")] | None = None


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_id: str | None
    body: str
    created_at: datetime
    client_id: str


class ConversationOut(BaseModel):
    id: str
    kind: Literal["direct", "team"]
    title: str
    project_id: str | None
    participants: list[dict]
    last_message_at: datetime | None
    last_message_preview: str | None
    unread: int
