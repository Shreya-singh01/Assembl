"""Socket.IO server.

Connections are authenticated with the same HTTP-only session cookie as the
REST API and must come from an allowed origin (prevents cross-site WebSocket
hijacking). Each socket joins only its user's private room. Message sends go
through the same service and authorization checks as the HTTP endpoint.
"""

from __future__ import annotations

import logging
from http.cookies import SimpleCookie

import socketio
from bson import ObjectId
from fastapi import HTTPException

from app.core.config import Settings
from app.core.serialize import plain
from app.services import auth as auth_service
from app.services import messaging

log = logging.getLogger(__name__)

MAX_CONNECTIONS_PER_USER = 10


def create_sio(settings: Settings) -> socketio.AsyncServer:
    manager = None
    if settings.redis_url:
        try:
            manager = socketio.AsyncRedisManager(settings.redis_url)
        except Exception as exc:  # noqa: BLE001 - single-instance fallback
            log.warning("Socket.IO Redis manager unavailable (%s); using in-process manager", exc.__class__.__name__)
    return socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins=settings.cors_origin_list,
        client_manager=manager,
        max_http_buffer_size=16_000,
        logger=False,
        engineio_logger=False,
    )


def register_handlers(sio: socketio.AsyncServer, app) -> None:
    connections: dict[str, int] = {}

    def _cookie(environ: dict, name: str) -> str | None:
        raw = environ.get("HTTP_COOKIE", "")
        jar = SimpleCookie()
        try:
            jar.load(raw)
        except Exception:  # noqa: BLE001
            return None
        return jar[name].value if name in jar else None

    @sio.event
    async def connect(sid, environ, auth=None):
        settings: Settings = app.state.settings
        origin = (environ.get("HTTP_ORIGIN") or "").rstrip("/")
        if origin and origin not in settings.cors_origin_list:
            raise socketio.exceptions.ConnectionRefusedError("origin not allowed")
        found = await auth_service.session_user(app.state.db, _cookie(environ, settings.session_cookie_name))
        if not found:
            raise socketio.exceptions.ConnectionRefusedError("not signed in")
        uid = str(found[1]["_id"])
        if connections.get(uid, 0) >= MAX_CONNECTIONS_PER_USER:
            raise socketio.exceptions.ConnectionRefusedError("too many connections")
        connections[uid] = connections.get(uid, 0) + 1
        await sio.save_session(sid, {"user_id": uid})
        await sio.enter_room(sid, f"user:{uid}")

    @sio.event
    async def disconnect(sid):
        try:
            uid = (await sio.get_session(sid)).get("user_id")
        except KeyError:
            return
        if uid and connections.get(uid):
            connections[uid] -= 1

    async def _user(sid) -> dict | None:
        try:
            uid = (await sio.get_session(sid)).get("user_id")
        except KeyError:
            return None
        return await app.state.db.users.find_one({"_id": ObjectId(uid)}) if uid else None

    @sio.on("message:send")
    async def message_send(sid, data):
        """Ack: {"ok": true, "message": {...}} or {"ok": false, "error": "..."}"""
        from app.api.routes.conversations import send_and_notify

        user = await _user(sid)
        if user is None:
            return {"ok": False, "error": "not signed in"}
        if not isinstance(data, dict) or not isinstance(data.get("body"), str) or not isinstance(data.get("conversation_id"), str):
            return {"ok": False, "error": "invalid payload"}
        client_id = data.get("client_id") if isinstance(data.get("client_id"), str) and 8 <= len(data["client_id"]) <= 64 else None
        try:
            msg = await send_and_notify(app, app.state.db, user, data["conversation_id"][:24], data["body"], client_id)
        except HTTPException as exc:
            return {"ok": False, "error": exc.detail}
        return {"ok": True, "message": plain(msg)}

    @sio.on("conversation:read")
    async def conversation_read(sid, data):
        user = await _user(sid)
        if user is None or not isinstance(data, dict) or not isinstance(data.get("conversation_id"), str):
            return {"ok": False}
        try:
            await messaging.mark_read(app.state.db, user, data["conversation_id"][:24])
        except HTTPException:
            return {"ok": False}
        return {"ok": True}

