"""Account deletion (right to withdraw).

Deleting an account removes, immediately and permanently:
* the user record, all sessions, the profile and every stored embedding;
* invitations and join requests the user sent or received;
* projects the user created (with their invitations and team conversation);
* the user's membership of other teams (their place reopens);
* messages the user sent, and direct conversations they took part in.
Research judgments the user gave as a rater are deleted too. Data already
exported into an offline evaluation report is not retroactively edited;
reports store candidate ids, never names or contact details.
"""

from __future__ import annotations

from app.services import messaging
from app.services.auth import now
from app.websocket.notifier import Notifier


async def delete_account(db, notifier: Notifier, user: dict) -> None:
    uid = user["_id"]
    owned = [p async for p in db.projects.find({"owner_id": uid})]
    owned_ids = [p["_id"] for p in owned]
    for p in owned:
        await notifier.to_users([m["user_id"] for m in p["members"] if m["user_id"] != uid], "team:update",
                                {"project_id": str(p["_id"]), "event": "deleted"})
    team_convs = [c["_id"] async for c in db.conversations.find({"project_id": {"$in": owned_ids}}, {"_id": 1})]
    await db.messages.delete_many({"conversation_id": {"$in": team_convs}})
    await db.conversations.delete_many({"_id": {"$in": team_convs}})
    await db.invitations.delete_many({"$or": [{"project_id": {"$in": owned_ids}}, {"from_user": uid}, {"candidate_id": uid}]})
    await db.projects.delete_many({"_id": {"$in": owned_ids}})

    async for p in db.projects.find({"members.user_id": uid}):
        member = next(m for m in p["members"] if m["user_id"] == uid)
        update = {"$pull": {"members": {"user_id": uid}}, "$inc": {"open_positions": 1, "version": 1},
                  "$push": {"history": {"at": now(), "type": "account_deleted", "user_id": None, "by": None}}}
        if member.get("role"):
            update["$addToSet"] = {"vacant_roles": member["role"]}
        updated = await db.projects.find_one_and_update({"_id": p["_id"]}, update, return_document=True)
        if updated:
            await messaging.sync_team_conversation(db, updated)

    direct = [c["_id"] async for c in db.conversations.find({"kind": "direct", "participant_ids": uid}, {"_id": 1})]
    await db.messages.delete_many({"$or": [{"sender_id": uid}, {"conversation_id": {"$in": direct}}]})
    await db.conversations.delete_many({"_id": {"$in": direct}})
    await db.judgments.delete_many({"rater_id": uid})
    await db.embeddings.delete_many({"user_id": uid})
    await db.profiles.delete_one({"_id": uid})
    await db.sessions.delete_many({"user_id": uid})
    await db.users.delete_one({"_id": uid})
