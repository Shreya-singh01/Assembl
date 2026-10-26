"""Conversations and messages. MongoDB is the source of truth; Socket.IO only
delivers notifications of what has already been stored.

Access rule: only participants can read or write a conversation; for anyone
else the conversation does not exist (404), so ids cannot be enumerated.
A direct conversation can be started with a user who is discoverable
(visible profile), shares a project, or is party to an invitation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.errors import bad_request, not_found, oid
from app.services.auth import now, user_brief
from app.services.profiles import is_discoverable
from app.services.projects import users_by_id

PREVIEW_CHARS = 80


async def _related(db, a: ObjectId, b: ObjectId) -> bool:
    if await db.projects.find_one({"members.user_id": {"$all": [a, b]}}, {"_id": 1}):
        return True
    return bool(await db.invitations.find_one(
        {"$or": [{"from_user": a, "candidate_id": b}, {"from_user": b, "candidate_id": a}]}, {"_id": 1}))


async def get_or_create_direct(db, me: dict, other_id: str) -> dict:
    other = oid(other_id, "User")
    if other == me["_id"]:
        raise bad_request("You cannot message yourself")
    if not await db.users.find_one({"_id": other}, {"_id": 1}):
        raise not_found("User")
    if not (await is_discoverable(db, other) or await _related(db, me["_id"], other)):
        raise not_found("User")
    key = ":".join(sorted([str(me["_id"]), str(other)]))
    existing = await db.conversations.find_one({"direct_key": key})
    if existing:
        return existing
    doc = {"kind": "direct", "direct_key": key, "participant_ids": [me["_id"], other], "project_id": None,
           "created_at": now(), "last_message_at": None, "last_message_preview": None, "reads": {}}
    try:
        res = await db.conversations.insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc
    except DuplicateKeyError:  # created concurrently
        return await db.conversations.find_one({"direct_key": key})


async def sync_team_conversation(db, project: dict) -> dict:
    members = [m["user_id"] for m in project["members"]]
    conv = await db.conversations.find_one_and_update(
        {"project_id": project["_id"], "kind": "team"},
        {"$set": {"participant_ids": members},
         "$setOnInsert": {"kind": "team", "project_id": project["_id"], "created_at": now(),
                          "last_message_at": None, "last_message_preview": None, "reads": {}}},
        upsert=True, return_document=True,
    )
    return conv


async def get_for_participant(db, me: dict, conversation_id: str) -> dict:
    conv = await db.conversations.find_one({"_id": oid(conversation_id, "Conversation"), "participant_ids": me["_id"]})
    if not conv:
        raise not_found("Conversation")
    return conv


def _read_at(conv: dict, uid: ObjectId) -> datetime | None:
    return (conv.get("reads") or {}).get(str(uid))


async def conversation_out(db, conv: dict, me: dict, users: dict | None = None) -> dict[str, Any]:
    users = users if users is not None else await users_by_id(db, conv["participant_ids"])
    flt: dict[str, Any] = {"conversation_id": conv["_id"], "sender_id": {"$ne": me["_id"]}}
    read_at = _read_at(conv, me["_id"])
    if read_at:
        flt["created_at"] = {"$gt": read_at}
    unread = await db.messages.count_documents(flt)
    title = None
    if conv["kind"] == "team":
        project = await db.projects.find_one({"_id": conv["project_id"]}, {"title": 1})
        title = f"Team: {project['title']}" if project else "Team"
    else:
        other = next((p for p in conv["participant_ids"] if p != me["_id"]), None)
        title = user_brief(users.get(other))["display_name"]
    return {
        "id": str(conv["_id"]),
        "kind": conv["kind"],
        "title": title,
        "project_id": str(conv["project_id"]) if conv.get("project_id") else None,
        "participants": [{**user_brief(users.get(p)), "id": str(p)} for p in conv["participant_ids"]],
        "last_message_at": conv.get("last_message_at"),
        "last_message_preview": conv.get("last_message_preview"),
        "unread": unread,
    }


async def list_conversations(db, me: dict, limit: int = 50) -> list[dict]:
    convs = [c async for c in db.conversations.find({"participant_ids": me["_id"]})
             .sort([("last_message_at", -1), ("_id", -1)]).limit(limit)]
    users = await users_by_id(db, [p for c in convs for p in c["participant_ids"]])
    return [await conversation_out(db, c, me, users) for c in convs]


def message_out(m: dict) -> dict[str, Any]:
    return {"id": str(m["_id"]), "conversation_id": str(m["conversation_id"]),
            "sender_id": str(m["sender_id"]) if m.get("sender_id") else None, "body": m["body"],
            "created_at": m["created_at"], "client_id": m["client_id"]}


async def list_messages(db, me: dict, conversation_id: str, before: str | None, limit: int) -> list[dict]:
    conv = await get_for_participant(db, me, conversation_id)
    flt: dict[str, Any] = {"conversation_id": conv["_id"]}
    if before:
        flt["_id"] = {"$lt": oid(before, "Message")}
    msgs = [m async for m in db.messages.find(flt).sort([("created_at", -1), ("_id", -1)]).limit(limit)]
    return [message_out(m) for m in reversed(msgs)]


async def send_message(db, me: dict, conversation_id: str, body: str, client_id: str | None,
                       max_chars: int) -> tuple[dict, dict]:
    body = body.strip()
    if not body:
        raise bad_request("Message is empty")
    if len(body) > max_chars:
        raise bad_request(f"Messages are limited to {max_chars} characters")
    conv = await get_for_participant(db, me, conversation_id)
    client_id = client_id or uuid.uuid4().hex
    msg = {"conversation_id": conv["_id"], "sender_id": me["_id"], "body": body, "created_at": now(),
           "client_id": client_id}
    try:
        res = await db.messages.insert_one(msg)
        msg["_id"] = res.inserted_id
    except DuplicateKeyError:  # retried send: return the stored message
        msg = await db.messages.find_one({"conversation_id": conv["_id"], "sender_id": me["_id"], "client_id": client_id})
        return message_out(msg), conv
    preview = body if len(body) <= PREVIEW_CHARS else body[:PREVIEW_CHARS - 1] + "…"
    await db.conversations.update_one(
        {"_id": conv["_id"]},
        {"$set": {"last_message_at": msg["created_at"], "last_message_preview": preview,
                  f"reads.{me['_id']}": msg["created_at"]}},
    )
    return message_out(msg), conv


async def mark_read(db, me: dict, conversation_id: str) -> None:
    conv = await get_for_participant(db, me, conversation_id)
    await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {f"reads.{me['_id']}": now()}})


async def unread_total(db, me: dict) -> int:
    return sum(c["unread"] for c in await list_conversations(db, me, limit=200))
