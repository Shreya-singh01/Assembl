"""Student profiles: storage, normalisation, completion and public views.

Stored shape (collection ``profiles``, ``_id`` = user ObjectId):
    skills: [{label (canonical), proficiency, kind, recognized, original}]
    declared_absent: [canonical labels]
    availability: [slot] | None      (None = not stated)
    ...
Names, e-mails and contact details live in ``users`` and are never part of
the domain profile used for ranking.
"""

from __future__ import annotations

from typing import Any

from app.domain.models import StudentProfile
from app.domain.parsing import profile_from_dict
from app.domain.semantic import TEXT_TEMPLATE_VERSION, profile_text
from app.domain.skills import SkillRegistry, default_registry
from app.schemas.profiles import ProfileIn
from app.services.auth import now

COMPLETION_FIELDS = {
    "skills": "Skills with proficiency",
    "roles": "Preferred team roles",
    "year_branch": "Year and branch",
    "interests_projects": "Interests or previous projects",
    "availability": "Weekly availability",
    "commitment": "Expected weekly hours",
    "work_mode": "Working mode",
}


def completion(doc: dict | None) -> dict[str, Any]:
    doc = doc or {}
    done = {
        "skills": bool(doc.get("skills")),
        "roles": bool(doc.get("primary_roles")),
        "year_branch": doc.get("year") is not None and bool(doc.get("branch")),
        "interests_projects": bool(doc.get("interests") or doc.get("projects")),
        "availability": doc.get("availability") is not None,
        "commitment": doc.get("weekly_hours") is not None,
        "work_mode": doc.get("work_mode") is not None,
    }
    return {
        "percent": round(100 * sum(done.values()) / len(done)),
        "missing": [COMPLETION_FIELDS[k] for k, v in done.items() if not v],
        "ready_for_matching": done["skills"],
    }


def normalize_input(data: ProfileIn, registry: SkillRegistry | None = None) -> tuple[dict, list[dict]]:
    registry = registry or default_registry()
    merged: dict[str, dict] = {}
    notes: list[dict] = []
    for s in data.skills:
        n = registry.normalize(s.label)
        if n.rule in ("alias", "compact") or n.original.strip() != n.canonical:
            notes.append({"original": s.label, "canonical": n.canonical, "rule": n.rule})
        key = n.canonical.casefold()
        prev = merged.get(key)
        if prev is None or s.proficiency > prev["proficiency"]:
            merged[key] = {"label": prev["label"] if prev else n.canonical, "proficiency": s.proficiency,
                           "kind": s.kind, "recognized": n.recognized, "original": s.label}
    skills = sorted(merged.values(), key=lambda x: x["label"].casefold())
    stated = {s["label"] for s in skills}
    absent = [a for a in registry.normalize_labels(data.declared_absent) if a not in stated]

    def dedupe(xs: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for x in xs:
            seen.setdefault(x.casefold(), x)
        return list(seen.values())

    primary = dedupe(data.primary_roles)
    secondary = [r for r in dedupe(data.secondary_roles) if r.casefold() not in {p.casefold() for p in primary}]
    doc = {
        "year": data.year,
        "branch": data.branch or None,
        "skills": skills,
        "declared_absent": absent,
        "primary_roles": primary,
        "secondary_roles": secondary,
        "interests": dedupe(data.interests),
        "projects": [p.model_dump(mode="json") for p in data.projects],
        "links": [str(u) for u in data.links],
        "availability": None if data.availability is None else sorted(set(data.availability)),
        "weekly_hours": data.weekly_hours,
        "work_mode": data.work_mode,
        "visible": data.visible,
    }
    return doc, notes


def to_domain(doc: dict) -> StudentProfile:
    return profile_from_dict(
        {
            "user_id": str(doc["_id"]),
            "skills": {s["label"]: s["proficiency"] for s in doc.get("skills", [])},
            "declared_absent": doc.get("declared_absent", []),
            "year": doc.get("year"),
            "branch": doc.get("branch"),
            "primary_roles": doc.get("primary_roles", []),
            "secondary_roles": doc.get("secondary_roles", []),
            "interests": doc.get("interests", []),
            "project_summaries": [
                " ".join(x for x in (p.get("title", ""), p.get("summary", ""), p.get("contribution", "")) if x)
                for p in doc.get("projects", [])
            ],
            "availability": doc.get("availability"),
            "weekly_hours": doc.get("weekly_hours"),
            "work_mode": doc.get("work_mode"),
            "visible": doc.get("visible", False),
        }
    )


def empty_profile(user_id) -> dict:
    return {"_id": user_id, "skills": [], "declared_absent": [], "primary_roles": [], "secondary_roles": [],
            "interests": [], "projects": [], "links": [], "availability": None, "weekly_hours": None,
            "work_mode": None, "visible": False, "year": None, "branch": None, "updated_at": None}


async def get_profile_doc(db, user_id) -> dict:
    return await db.profiles.find_one({"_id": user_id}) or empty_profile(user_id)


async def save_profile(db, user_id, data: ProfileIn) -> tuple[dict, list[dict]]:
    doc, notes = normalize_input(data)
    doc["updated_at"] = now()
    text = profile_text(to_domain({"_id": user_id, **doc}))
    doc["text"] = text
    doc["text_version"] = TEXT_TEMPLATE_VERSION
    await db.profiles.update_one({"_id": user_id}, {"$set": doc}, upsert=True)
    # Profile text changed -> cached embeddings for other text are stale; the
    # embedding store also checks the text hash, this just frees space early.
    await db.embeddings.delete_many({"user_id": user_id, "text": {"$ne": text}})
    return {"_id": user_id, **doc}, notes


def profile_out(doc: dict, notes: list[dict] | None = None) -> dict[str, Any]:
    return {
        "user_id": str(doc["_id"]),
        "year": doc.get("year"),
        "branch": doc.get("branch"),
        "skills": [{k: s[k] for k in ("label", "proficiency", "kind", "recognized")} for s in doc.get("skills", [])],
        "declared_absent": doc.get("declared_absent", []),
        "primary_roles": doc.get("primary_roles", []),
        "secondary_roles": doc.get("secondary_roles", []),
        "interests": doc.get("interests", []),
        "projects": doc.get("projects", []),
        "links": doc.get("links", []),
        "availability": doc.get("availability"),
        "weekly_hours": doc.get("weekly_hours"),
        "work_mode": doc.get("work_mode"),
        "visible": doc.get("visible", False),
        "completion": completion(doc),
        "updated_at": doc.get("updated_at"),
        "normalization": notes or [],
    }


def public_profile(doc: dict, user: dict) -> dict[str, Any]:
    return {
        "user_id": str(doc["_id"]),
        "display_name": user["display_name"],
        "handle": user["handle"],
        "year": doc.get("year"),
        "branch": doc.get("branch"),
        "skills": [{k: s[k] for k in ("label", "proficiency", "kind", "recognized")} for s in doc.get("skills", [])],
        "primary_roles": doc.get("primary_roles", []),
        "secondary_roles": doc.get("secondary_roles", []),
        "interests": doc.get("interests", []),
        "projects": doc.get("projects", []),
        "links": doc.get("links", []),
        "weekly_hours": doc.get("weekly_hours"),
        "work_mode": doc.get("work_mode"),
        "availability_stated": doc.get("availability") is not None,
    }


async def is_discoverable(db, user_id) -> bool:
    """``visible`` is the student's explicit opt-in to being shown to teams."""
    prof = await db.profiles.find_one({"_id": user_id}, {"visible": 1})
    return bool(prof and prof.get("visible"))
