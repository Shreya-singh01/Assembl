"""Projects (recruitment requests) and their team membership documents.

A project document holds its members and an ``open_positions`` counter
(target_size - len(members)). Every membership change is a single
conditional update on this one document, which MongoDB applies atomically, so
concurrent acceptances cannot exceed the target size. ``version`` is bumped
on every change and used for optimistic concurrency on edits.
"""

from __future__ import annotations

import re
from typing import Any

from bson import ObjectId

from app.core.errors import bad_request, conflict, forbidden, not_found, oid
from app.domain.models import DomainValidationError, ProjectSpec
from app.domain.parsing import project_from_dict
from app.domain.skills import default_registry
from app.schemas.projects import ProjectIn, ProjectUpdateIn
from app.services.auth import now, user_brief

SETTINGS_FIELDS = (
    "title", "description", "opportunity_type", "event_key", "target_size", "vacant_roles", "allowed_years",
    "role_mandatory", "synchronous", "min_shared_slots", "availability_policy", "availability_mandatory",
    "weekly_hours", "work_mode", "unverifiable_policy", "visibility",
)


def normalize_requirements(reqs) -> list[dict]:
    reg = default_registry()
    out: dict[str, dict] = {}
    for r in reqs:
        canonical = reg.normalize(r.skill).canonical
        key = canonical.casefold()
        if key in out:
            raise bad_request(f"'{r.skill}' duplicates another required skill ({canonical})")
        out[key] = {"skill": canonical, "importance": r.importance, "desired_proficiency": r.desired_proficiency,
                    "mandatory": r.mandatory}
    return list(out.values())


def _dedupe_roles(roles: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for r in roles:
        seen.setdefault(r.casefold(), r)
    return list(seen.values())


def to_spec(doc: dict) -> ProjectSpec:
    return project_from_dict({
        "project_id": str(doc["_id"]),
        "title": doc.get("title", ""),
        "description": doc.get("description", ""),
        "requirements": doc["requirements"],
        "target_size": doc["target_size"],
        "vacant_roles": doc.get("vacant_roles", []),
        "allowed_years": doc.get("allowed_years"),
        "role_mandatory": doc.get("role_mandatory", False),
        "synchronous": doc.get("synchronous", False),
        "min_shared_slots": doc.get("min_shared_slots", 0),
        "availability_policy": doc.get("availability_policy", "all"),
        "availability_mandatory": doc.get("availability_mandatory", False),
        "weekly_hours": doc.get("weekly_hours"),
        "work_mode": doc.get("work_mode"),
        "unverifiable_policy": doc.get("unverifiable_policy", "exclude"),
    })


def _settings_from(data: ProjectIn) -> dict[str, Any]:
    d = data.model_dump()
    out = {k: d[k] for k in SETTINGS_FIELDS}
    out["vacant_roles"] = _dedupe_roles(data.vacant_roles)
    out["allowed_years"] = sorted(set(data.allowed_years)) if data.allowed_years else None
    out["requirements"] = normalize_requirements(data.requirements)
    return out


def _validate_domain(doc: dict) -> None:
    try:
        to_spec({"_id": "validation", **doc})
    except DomainValidationError as exc:
        raise bad_request(str(exc)) from None


async def create_project(db, owner: dict, data: ProjectIn) -> dict:
    settings = _settings_from(data)
    doc = {
        **settings,
        "owner_id": owner["_id"],
        "members": [{"user_id": owner["_id"], "role": data.creator_role, "joined_at": now()}],
        "open_positions": data.target_size - 1,
        "status": "open",
        "history": [{"at": now(), "type": "created", "user_id": owner["_id"], "by": owner["_id"]}],
        "created_at": now(),
        "updated_at": now(),
        "version": 0,
    }
    if data.creator_role:
        doc["vacant_roles"] = [r for r in doc["vacant_roles"] if r.casefold() != data.creator_role.casefold()]
    _validate_domain(doc)
    if data.event_key and await db.projects.find_one({"event_key": data.event_key, "members.user_id": owner["_id"]}):
        raise conflict("You are already on a team for this event")
    res = await db.projects.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


async def update_project(db, user: dict, project_id: str, data: ProjectUpdateIn) -> dict:
    doc = await db.projects.find_one({"_id": oid(project_id, "Project")})
    if not doc or not can_view(doc, user):
        raise not_found("Project")
    if doc["owner_id"] != user["_id"]:
        raise forbidden("Only the project creator can edit it")
    settings = _settings_from(data)
    members = len(doc["members"])
    if data.target_size < members:
        raise bad_request(f"Target size cannot be below the current team size ({members})")
    update = {**settings, "status": data.status, "open_positions": data.target_size - members, "updated_at": now()}
    _validate_domain({**doc, **update})
    res = await db.projects.find_one_and_update(
        # same version and same member count: no concurrent edit or join happened
        {"_id": doc["_id"], "version": data.version, "members": {"$size": members}},
        {"$set": update, "$inc": {"version": 1},
         "$push": {"history": {"at": now(), "type": "edited", "user_id": user["_id"], "by": user["_id"]}}},
        return_document=True,
    )
    if res is None:
        raise conflict("The project changed while you were editing it; reload and try again")
    return res


def is_member(doc: dict, user_id) -> bool:
    return any(m["user_id"] == user_id for m in doc.get("members", []))


def can_view(doc: dict, user: dict | None) -> bool:
    if doc.get("visibility", "public") == "public":
        return True
    return user is not None and (doc["owner_id"] == user["_id"] or is_member(doc, user["_id"]))


async def get_project_for(db, project_id: str, user: dict | None) -> dict:
    doc = await db.projects.find_one({"_id": oid(project_id, "Project")})
    if not doc or not (can_view(doc, user) or (user and await db.invitations.find_one(
            {"project_id": doc["_id"], "candidate_id": user["_id"]}, {"_id": 1}))):
        raise not_found("Project")
    return doc


async def list_projects(db, user: dict | None, *, q: str | None, opportunity_type: str | None, skill: str | None,
                        status: str | None, mine: bool, limit: int, offset: int) -> tuple[list[dict], int]:
    flt: dict[str, Any] = {}
    if mine:
        if not user:
            return [], 0
        flt["members.user_id"] = user["_id"]
    else:
        flt["visibility"] = "public"
    if status:
        flt["status"] = status
    if opportunity_type:
        flt["opportunity_type"] = opportunity_type
    if skill:
        canonical = default_registry().normalize(skill).canonical
        flt["requirements.skill"] = {"$regex": f"^{re.escape(canonical)}$", "$options": "i"}
    if q:
        pattern = {"$regex": re.escape(q.strip()[:80]), "$options": "i"}
        flt["$or"] = [{"title": pattern}, {"description": pattern}]
    total = await db.projects.count_documents(flt)
    cursor = db.projects.find(flt, {"embedding": 0}).sort([("created_at", -1), ("_id", -1)]).skip(offset).limit(limit)
    return [d async for d in cursor], total


async def users_by_id(db, ids) -> dict[ObjectId, dict]:
    ids = list({i for i in ids if i is not None})
    return {u["_id"]: u async for u in db.users.find({"_id": {"$in": ids}}, {"display_name": 1, "handle": 1})}


async def project_out(db, doc: dict, viewer: dict | None, users: dict | None = None) -> dict[str, Any]:
    users = users if users is not None else await users_by_id(db, [m["user_id"] for m in doc["members"]])
    vid = viewer["_id"] if viewer else None
    rel: dict[str, Any] = {"is_owner": vid == doc["owner_id"], "is_member": bool(vid and is_member(doc, vid))}
    if vid and not rel["is_member"]:
        pending = await db.invitations.find_one({"project_id": doc["_id"], "candidate_id": vid, "status": "pending"})
        rel["pending_invitation"] = None if not pending else {"id": str(pending["_id"]), "kind": pending["kind"]}
    return {
        "id": str(doc["_id"]),
        "owner_id": str(doc["owner_id"]),
        **{k: doc.get(k) for k in SETTINGS_FIELDS},
        "requirements": doc["requirements"],
        "open_positions": doc["open_positions"],
        "status": doc["status"],
        "members": [
            {**{k: v for k, v in user_brief(users.get(m["user_id"])).items() if k != "id"},
             "user_id": str(m["user_id"]), "role": m.get("role"), "joined_at": m["joined_at"],
             "is_owner": m["user_id"] == doc["owner_id"]}
            for m in doc["members"]
        ],
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
        "version": doc.get("version", 0),
        "viewer": rel,
    }
