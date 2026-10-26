"""Invitations, join requests and team membership changes.

Accepting (concurrency-safe, no multi-document transaction needed):

1. Claim the invitation: ``pending -> accepting`` with a conditional update.
   Only one request can win the claim.
2. Join the team with one conditional update on the project document:
   ``{status: open, open_positions > 0, members.user_id != candidate}`` ->
   ``$inc open_positions -1, $push member``. MongoDB applies single-document
   updates atomically, so two acceptances racing for the last place cannot
   both succeed.
3. Finalise the invitation as ``accepted``, or - if step 2 matched nothing -
   compensate by marking it ``expired`` with reason ``team_full_or_closed``.

``candidate_id`` is always the student who would join: the invitee for an
invitation, the requester for a join request.
"""

from __future__ import annotations

from typing import Any, Literal

from pymongo.errors import DuplicateKeyError

from app.core.errors import bad_request, conflict, forbidden, not_found, oid
from app.services import messaging
from app.services.auth import now, user_brief
from app.services.profiles import is_discoverable
from app.services.projects import get_project_for, is_member, users_by_id
from app.websocket.notifier import Notifier


async def _committed_to_event(db, project: dict, candidate_id) -> bool:
    if not project.get("event_key"):
        return False
    return bool(await db.projects.find_one(
        {"event_key": project["event_key"], "_id": {"$ne": project["_id"]}, "members.user_id": candidate_id}, {"_id": 1}))


async def _create(db, project: dict, kind: str, from_user, candidate_id, role: str | None, message: str) -> dict:
    if project["status"] != "open" or project["open_positions"] <= 0:
        raise conflict("This team is not recruiting")
    if is_member(project, candidate_id):
        raise conflict("Already a member of this team")
    if await _committed_to_event(db, project, candidate_id):
        raise conflict("Already on another team for the same event")
    if role:
        match = [r for r in project.get("vacant_roles", []) if r.casefold() == role.casefold()]
        if not match:
            raise bad_request("That role is not vacant in this team")
        role = match[0]  # stored spelling, so $pull on acceptance matches exactly
    if await db.invitations.find_one({"project_id": project["_id"], "candidate_id": candidate_id, "status": "pending"}):
        raise conflict("There is already a pending invitation or request for this team")
    doc = {"project_id": project["_id"], "kind": kind, "from_user": from_user, "candidate_id": candidate_id,
           "role": role, "message": message, "status": "pending", "reason": None, "created_at": now(),
           "responded_at": None}
    try:
        res = await db.invitations.insert_one(doc)
    except DuplicateKeyError:
        raise conflict("There is already a pending invitation or request for this team") from None
    doc["_id"] = res.inserted_id
    return doc


async def invite(db, notifier: Notifier, owner: dict, project_id: str, candidate_id: str,
                 role: str | None, message: str) -> dict:
    project = await get_project_for(db, project_id, owner)
    if project["owner_id"] != owner["_id"]:
        raise forbidden("Only the project creator can send invitations")
    cand = oid(candidate_id, "Student")
    if cand == owner["_id"] or not await db.users.find_one({"_id": cand}, {"_id": 1}) or not await is_discoverable(db, cand):
        raise not_found("Student")
    doc = await _create(db, project, "invite", owner["_id"], cand, role, message)
    await notifier.to_users([cand], "invitation:new", {"id": str(doc["_id"]), "project_id": project_id})
    return doc


async def invite_by_handle(db, notifier: Notifier, owner: dict, project_id: str, handle: str,
                           role: str | None, message: str) -> dict:
    user = await db.users.find_one({"handle_key": handle.lower()}, {"_id": 1})
    if not user:
        raise not_found("Student")
    return await invite(db, notifier, owner, project_id, str(user["_id"]), role, message)


async def request_to_join(db, notifier: Notifier, user: dict, project_id: str, role: str | None, message: str) -> dict:
    project = await get_project_for(db, project_id, user)
    if project.get("visibility") != "public":
        raise not_found("Project")
    doc = await _create(db, project, "request", user["_id"], user["_id"], role, message)
    await notifier.to_users([project["owner_id"]], "invitation:new", {"id": str(doc["_id"]), "project_id": project_id})
    return doc


def _responder_allowed(inv: dict, project: dict, user_id, action: str) -> bool:
    if action == "cancel":
        return inv["from_user"] == user_id
    # accept/decline: the other party
    if inv["kind"] == "invite":
        return inv["candidate_id"] == user_id
    return project["owner_id"] == user_id


async def respond(db, notifier: Notifier, user: dict, invitation_id: str,
                  action: Literal["accept", "decline", "cancel"]) -> dict:
    inv = await db.invitations.find_one({"_id": oid(invitation_id, "Invitation")})
    if not inv:
        raise not_found("Invitation")
    project = await db.projects.find_one({"_id": inv["project_id"]})
    parties = {inv["from_user"], inv["candidate_id"], project["owner_id"] if project else None}
    if user["_id"] not in parties:
        raise not_found("Invitation")
    if not project or not _responder_allowed(inv, project, user["_id"], action):
        raise forbidden("You cannot do that with this invitation")
    if inv["status"] != "pending":
        raise conflict(f"This invitation is already {inv['status']}")

    if action in ("decline", "cancel"):
        status = "declined" if action == "decline" else "cancelled"
        res = await db.invitations.find_one_and_update(
            {"_id": inv["_id"], "status": "pending"}, {"$set": {"status": status, "responded_at": now()}},
            return_document=True)
        if res is None:
            raise conflict("This invitation was already answered")
        await notifier.to_users(parties - {None}, "invitation:update", {"id": invitation_id, "status": status})
        return res

    # --- accept -----------------------------------------------------------
    claimed = await db.invitations.find_one_and_update(
        {"_id": inv["_id"], "status": "pending"}, {"$set": {"status": "accepting"}})
    if claimed is None:
        raise conflict("This invitation was already answered")
    cand = inv["candidate_id"]
    if await _committed_to_event(db, project, cand):
        await _finish(db, inv, "expired", "already_on_event_team")
        raise conflict("The student is already on another team for the same event")
    update: dict[str, Any] = {
        "$inc": {"open_positions": -1, "version": 1},
        "$push": {
            "members": {"user_id": cand, "role": inv.get("role"), "joined_at": now()},
            "history": {"at": now(), "type": "joined", "user_id": cand, "by": user["_id"], "invitation_id": inv["_id"]},
        },
        "$set": {"updated_at": now()},
    }
    if inv.get("role"):
        update["$pull"] = {"vacant_roles": inv["role"]}
    joined = await db.projects.find_one_and_update(
        {"_id": project["_id"], "status": "open", "open_positions": {"$gt": 0}, "members.user_id": {"$ne": cand}},
        update, return_document=True)
    if joined is None:
        await _finish(db, inv, "expired", "team_full_or_closed")
        raise conflict("The team is full or no longer recruiting")
    result = await _finish(db, inv, "accepted", None)
    await messaging.sync_team_conversation(db, joined)
    if joined["open_positions"] == 0:
        await _expire_pending(db, joined["_id"], "team_full")
    members = [m["user_id"] for m in joined["members"]]
    await notifier.to_users(set(members) | parties - {None}, "team:update",
                            {"project_id": str(joined["_id"]), "event": "joined", "user_id": str(cand)})
    await notifier.to_users(parties - {None}, "invitation:update", {"id": invitation_id, "status": "accepted"})
    return result


async def _finish(db, inv: dict, status: str, reason: str | None) -> dict:
    return await db.invitations.find_one_and_update(
        {"_id": inv["_id"]}, {"$set": {"status": status, "reason": reason, "responded_at": now()}},
        return_document=True)


async def _expire_pending(db, project_id, reason: str) -> None:
    await db.invitations.update_many({"project_id": project_id, "status": "pending"},
                                     {"$set": {"status": "expired", "reason": reason, "responded_at": now()}})


async def remove_member(db, notifier: Notifier, user: dict, project_id: str, member_id: str) -> dict:
    project = await get_project_for(db, project_id, user)
    target = oid(member_id, "Member")
    if target == project["owner_id"]:
        raise bad_request("The project creator cannot leave or be removed; close the project instead")
    if user["_id"] not in (target, project["owner_id"]):
        raise forbidden("Only the project creator can remove other members")
    member = next((m for m in project["members"] if m["user_id"] == target), None)
    if member is None:
        raise not_found("Member")
    update: dict[str, Any] = {
        "$pull": {"members": {"user_id": target}},
        "$inc": {"open_positions": 1, "version": 1},
        "$push": {"history": {"at": now(), "type": "left" if target == user["_id"] else "removed",
                              "user_id": target, "by": user["_id"]}},
        "$set": {"updated_at": now()},
    }
    if member.get("role"):
        update["$addToSet"] = {"vacant_roles": member["role"]}
    updated = await db.projects.find_one_and_update({"_id": project["_id"], "members.user_id": target}, update,
                                                     return_document=True)
    if updated is None:
        raise conflict("Membership changed concurrently; reload and try again")
    await messaging.sync_team_conversation(db, updated)
    await notifier.to_users([m["user_id"] for m in project["members"]], "team:update",
                            {"project_id": project_id, "event": "left", "user_id": member_id})
    return updated


async def list_invitations(db, user: dict, box: Literal["received", "sent"], status: str | None) -> list[dict]:
    uid = user["_id"]
    owned = [p["_id"] async for p in db.projects.find({"owner_id": uid}, {"_id": 1})]
    if box == "received":
        flt: dict[str, Any] = {"$or": [{"kind": "invite", "candidate_id": uid},
                                       {"kind": "request", "project_id": {"$in": owned}}]}
    else:
        flt = {"from_user": uid}
    if status:
        flt["status"] = status
    invs = [i async for i in db.invitations.find(flt).sort("created_at", -1).limit(100)]
    return await invitations_out(db, invs)


async def invitations_out(db, invs: list[dict]) -> list[dict]:
    users = await users_by_id(db, [u for i in invs for u in (i["from_user"], i["candidate_id"])])
    titles = {p["_id"]: p["title"] async for p in db.projects.find(
        {"_id": {"$in": list({i["project_id"] for i in invs})}}, {"title": 1})}
    return [{
        "id": str(i["_id"]), "project_id": str(i["project_id"]), "project_title": titles.get(i["project_id"], "Deleted project"),
        "kind": i["kind"], "from_user": user_brief(users.get(i["from_user"])), "candidate": user_brief(users.get(i["candidate_id"])),
        "role": i.get("role"), "message": i.get("message", ""), "status": i["status"], "reason": i.get("reason"),
        "created_at": i["created_at"], "responded_at": i.get("responded_at"),
    } for i in invs]
