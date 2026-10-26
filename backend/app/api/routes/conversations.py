"""/api/v1/conversations - persistent messaging (Socket.IO delivers live updates)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.deps import CurrentUser, Db, SettingsDep
from app.schemas.social import ConversationOut, MessageOut, SendMessageIn, StartConversationIn
from app.services import messaging

router = APIRouter(prefix="/conversations", tags=["messaging"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(user: CurrentUser, db: Db):
    return await messaging.list_conversations(db, user)


@router.post("", response_model=ConversationOut, responses={404: {}})
async def start_conversation(data: StartConversationIn, user: CurrentUser, db: Db):
    conv = await messaging.get_or_create_direct(db, user, data.user_id)
    return await messaging.conversation_out(db, conv, user)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut], responses={404: {}})
async def get_messages(conversation_id: str, user: CurrentUser, db: Db,
                       before: str | None = Query(None, max_length=24), limit: int = Query(50, ge=1, le=100)):
    return await messaging.list_messages(db, user, conversation_id, before, limit)


async def send_and_notify(app, db, user: dict, conversation_id: str, body: str, client_id: str | None) -> dict:
    settings = app.state.settings
    if not await app.state.rate_limiter.hit(f"msg:{user['_id']}", settings.message_rate_limit, settings.message_rate_window_s):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "You are sending messages too quickly")
    msg, conv = await messaging.send_message(db, user, conversation_id, body, client_id, settings.max_message_chars)
    await app.state.notifier.to_users(conv["participant_ids"], "message:new", msg)
    return msg


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=201, responses={404: {}, 429: {}})
async def send_message(conversation_id: str, data: SendMessageIn, request: Request, user: CurrentUser, db: Db,
                       settings: SettingsDep):
    return await send_and_notify(request.app, db, user, conversation_id, data.body, data.client_id)


@router.post("/{conversation_id}/read", status_code=204, responses={404: {}})
async def mark_read(conversation_id: str, user: CurrentUser, db: Db):
    await messaging.mark_read(db, user, conversation_id)
