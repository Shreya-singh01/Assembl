"""/api/v1/profiles - own profile, public profiles, skill vocabulary."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, Db
from app.core.errors import not_found, oid
from app.domain.models import PROFICIENCY_LABELS
from app.domain.skills import default_registry
from app.schemas.profiles import ProfileIn, ProfileOut, PublicProfileOut
from app.services import profiles as svc
from app.services.projects import is_member

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileOut)
async def get_my_profile(user: CurrentUser, db: Db):
    return svc.profile_out(await svc.get_profile_doc(db, user["_id"]))


@router.put("/me", response_model=ProfileOut, responses={422: {"description": "Validation error"}})
async def put_my_profile(data: ProfileIn, user: CurrentUser, db: Db):
    doc, notes = await svc.save_profile(db, user["_id"], data)
    return svc.profile_out(doc, notes)


@router.get("/vocabulary")
async def vocabulary():
    """Canonical skill labels, proficiency anchors and suggested roles for forms."""
    return {
        "skills": default_registry().canonical_labels,
        "proficiency": PROFICIENCY_LABELS,
        "roles": ["Frontend", "Backend", "Full-stack", "ML", "Data", "Designer", "Mobile", "DevOps", "Presenter",
                  "Researcher", "Hardware", "Product", "Writer"],
    }


@router.get("/{user_id}", response_model=PublicProfileOut, responses={404: {}})
async def get_public_profile(user_id: str, user: CurrentUser, db: Db):
    """Visible profiles are public to signed-in users; hidden profiles are
    visible only to people who share a team with that student."""
    uid = oid(user_id, "Profile")
    doc = await db.profiles.find_one({"_id": uid})
    owner = await db.users.find_one({"_id": uid}, {"display_name": 1, "handle": 1})
    if not doc or not owner:
        raise not_found("Profile")
    if not doc.get("visible") and uid != user["_id"]:
        shared = await db.projects.find_one({"members.user_id": {"$all": [uid, user["_id"]]}}, {"members": 1})
        if not shared or not (is_member(shared, uid) and is_member(shared, user["_id"])):
            raise not_found("Profile")
    return svc.public_profile(doc, owner)
