"""Push events to connected users over Socket.IO.

Every user joins the private room ``user:<id>`` on connect, so an event is
delivered only to the users it is addressed to - never broadcast.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from app.core.serialize import plain

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, sio=None):
        self.sio = sio

    async def to_users(self, user_ids: Iterable, event: str, data: dict[str, Any]) -> None:
        if self.sio is None:
            return
        payload = plain(data)  # datetimes / ObjectIds -> JSON-safe values
        for uid in {str(u) for u in user_ids}:
            try:
                await self.sio.emit(event, payload, room=f"user:{uid}")
            except Exception as exc:  # noqa: BLE001 - realtime delivery is best effort; MongoDB is the source of truth
                log.warning("socket emit failed: %s", exc.__class__.__name__)
