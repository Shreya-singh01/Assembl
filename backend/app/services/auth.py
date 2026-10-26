"""Accounts and server-side sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.core.errors import conflict
from app.core.security import DUMMY_HASH, hash_password, new_token, token_digest, verify_password


def now() -> datetime:
    return datetime.now(timezone.utc)


async def register(db, settings: Settings, email: str, password: str, display_name: str, handle: str) -> dict:
    email = email.strip().lower()
    doc = {
        "email": email,
        "password_hash": hash_password(password),
        "display_name": display_name,
        "handle": handle,
        "handle_key": handle.lower(),
        "role": "admin" if email in settings.admin_email_set else "student",
        "created_at": now(),
        "consent": {"terms_accepted_at": now(), "research_participation": False},
    }
    if await db.users.find_one({"$or": [{"email": email}, {"handle_key": doc["handle_key"]}]}, {"_id": 1}):
        raise conflict("An account with that e-mail or handle already exists")
    try:
        res = await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise conflict("An account with that e-mail or handle already exists") from None
    doc["_id"] = res.inserted_id
    return doc


async def authenticate(db, email: str, password: str) -> dict | None:
    user = await db.users.find_one({"email": email.strip().lower()})
    if not user:
        verify_password(password, DUMMY_HASH)  # equalise timing
        return None
    return user if verify_password(password, user["password_hash"]) else None


async def create_session(db, settings: Settings, user_id) -> tuple[str, dict]:
    token = new_token()
    session = {
        "_id": token_digest(token),
        "user_id": user_id,
        "csrf_token": new_token(),
        "created_at": now(),
        "last_seen": now(),
        "expires_at": now() + timedelta(hours=settings.session_ttl_hours),
    }
    await db.sessions.insert_one(session)
    return token, session


async def session_user(db, token: str | None) -> tuple[dict, dict] | None:
    if not token or len(token) > 128:
        return None
    session = await db.sessions.find_one({"_id": token_digest(token)})
    if not session:
        return None
    expires = session["expires_at"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now():
        await db.sessions.delete_one({"_id": session["_id"]})
        return None
    user = await db.users.find_one({"_id": session["user_id"]})
    if not user:
        return None
    return session, user


async def destroy_session(db, token: str | None) -> None:
    if token:
        await db.sessions.delete_one({"_id": token_digest(token)})


async def destroy_all_sessions(db, user_id) -> None:
    await db.sessions.delete_many({"user_id": user_id})


def user_out(user: dict, profile_complete: bool = False) -> dict[str, Any]:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "display_name": user["display_name"],
        "handle": user["handle"],
        "role": user.get("role", "student"),
        "created_at": user["created_at"],
        "consent": {k: v for k, v in user.get("consent", {}).items()},
        "profile_complete": profile_complete,
    }


def user_brief(user: dict | None) -> dict[str, Any]:
    if not user:
        return {"id": None, "display_name": "Deleted user", "handle": None}
    return {"id": str(user["_id"]), "display_name": user["display_name"], "handle": user["handle"]}
