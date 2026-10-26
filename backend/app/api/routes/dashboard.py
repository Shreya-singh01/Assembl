"""/api/v1/dashboard and /api/v1/health."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUser, Db
from app.domain.semantic import cosine_clipped
from app.services import messaging, profiles, teams
from app.services import projects as projects_svc
from app.services.embedding_store import EmbeddingStore

router = APIRouter(tags=["dashboard"])
health = APIRouter(prefix="/health", tags=["health"])


@router.get("/dashboard")
async def dashboard(user: CurrentUser, db: Db, request: Request):
    """Everything on the student dashboard in one call. Only real data; empty
    lists when there is nothing yet."""
    prof = await db.profiles.find_one({"_id": user["_id"]})
    mine, _ = await projects_svc.list_projects(db, user, q=None, opportunity_type=None, skill=None, status=None,
                                              mine=True, limit=20, offset=0)
    received = await teams.list_invitations(db, user, "received", "pending")
    sent = await teams.list_invitations(db, user, "sent", None)
    convs = await messaging.list_conversations(db, user, limit=5)
    suggested = await _suggested_projects(db, request.app.state.embedding_store, user, prof)
    users = await projects_svc.users_by_id(db, [m["user_id"] for d in mine for m in d["members"]])
    return {
        "profile_completion": profiles.completion(prof),
        "profile_visible": bool(prof and prof.get("visible")),
        "my_projects": [await projects_svc.project_out(db, d, user, users) for d in mine],
        "pending_received": received,
        "recent_sent": sent[:10],
        "recent_conversations": convs,
        "suggested_projects": suggested,
    }


async def _suggested_projects(db, store: EmbeddingStore, user: dict, prof: dict | None) -> list[dict]:
    """Open public projects ordered by semantic relevance of the student's
    profile to the project (f_sem only). A convenience for discovery; it is not
    the team-aware ranking, which runs from the team's side."""
    if not prof or not prof.get("skills"):
        return []
    docs = [d async for d in db.projects.find(
        {"status": "open", "visibility": "public", "open_positions": {"$gt": 0}, "members.user_id": {"$ne": user["_id"]}}
    ).sort("created_at", -1).limit(30)]
    if not docs:
        return []
    pvec = (await store.profile_vectors([prof])).get(str(prof["_id"]))
    if pvec is None:
        return []
    scored = []
    for d in docs:
        scored.append((cosine_clipped(pvec, await store.project_vector(d)), d))
    scored.sort(key=lambda t: (-t[0], str(t[1]["_id"])))
    return [{"id": str(d["_id"]), "title": d["title"], "opportunity_type": d["opportunity_type"],
             "open_positions": d["open_positions"], "vacant_roles": d.get("vacant_roles", []),
             "semantic_relevance": round(s, 3)} for s, d in scored[:5]]


@health.get("")
async def liveness():
    return {"status": "ok"}


@health.get("/ready")
async def readiness(request: Request):
    state = request.app.state
    checks = {"database": False, "encoder": state.encoder.model_id,
              "encoder_loaded": getattr(state.encoder, "loaded", True)}
    try:
        await state.db.command("ping")
        checks["database"] = True
    except Exception:  # noqa: BLE001
        pass
    return JSONResponse({"ready": checks["database"], **checks}, status_code=200 if checks["database"] else 503)
