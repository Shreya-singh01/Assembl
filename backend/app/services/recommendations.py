"""Glue between stored documents and the pure ranking engine.

Recommendations are computed on request and not cached: the result depends on
team membership, every candidate profile, the requirements, the weights and
the model version, and the computation is cheap once embeddings are cached.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import anyio
from bson import ObjectId

from app.core.errors import forbidden
from app.domain.engine import RankingResult, rank_candidates
from app.domain.features import FeatureValue
from app.domain.models import IMPORTANCE_LABELS, RecommendationRequest
from app.domain.scoring import FEATURE_LABELS, INITIAL_WEIGHTS
from app.services.embedding_store import EmbeddingStore
from app.services.profiles import empty_profile, public_profile, to_domain
from app.services.projects import get_project_for, to_spec, users_by_id

MAX_POOL = 2000


def _feature(fv: FeatureValue) -> dict[str, Any]:
    return {"value": fv.value, "status": fv.status}


def coverage_out(result: RankingResult, spec) -> dict[str, Any]:
    mandatory = {r.skill: r.mandatory for r in spec.requirements}
    return {
        "overall": result.team_coverage.overall,
        "complete": result.team_coverage.complete,
        "per_skill": [{
            "skill": s.skill, "importance": s.importance, "importance_label": IMPORTANCE_LABELS[s.importance],
            "desired_proficiency": s.desired_proficiency, "best_proficiency": s.best_proficiency,
            "coverage": s.coverage, "mandatory": mandatory[s.skill],
        } for s in result.team_coverage.per_skill],
    }


async def build_request(db, store: EmbeddingStore, project: dict) -> tuple[RecommendationRequest, dict[str, dict]]:
    member_ids = [m["user_id"] for m in project["members"]]
    team_docs = {d["_id"]: d async for d in db.profiles.find({"_id": {"$in": member_ids}})}
    team = tuple(to_domain(team_docs.get(uid) or empty_profile(uid)) for uid in member_ids)
    # Hidden profiles never leave the database; eligibility re-checks visibility anyway.
    cand_docs = [d async for d in db.profiles.find({"visible": True, "_id": {"$nin": member_ids}})
                 .sort("_id", 1).limit(MAX_POOL)]
    committed: set[str] = set()
    if project.get("event_key"):
        async for other in db.projects.find({"event_key": project["event_key"], "_id": {"$ne": project["_id"]}},
                                            {"members.user_id": 1}):
            committed.update(str(m["user_id"]) for m in other["members"])
    semantic = await store.semantic(project, cand_docs) if cand_docs else {}
    request = RecommendationRequest(
        project=to_spec(project), team=team, candidates=tuple(to_domain(d) for d in cand_docs),
        semantic=semantic, committed_elsewhere=frozenset(committed),
    )
    return request, {str(d["_id"]): d for d in cand_docs}


async def recommend(db, store: EmbeddingStore, user: dict, project_id: str, *, limit: int, offset: int,
                    timeout_s: float) -> dict[str, Any]:
    project = await get_project_for(db, project_id, user)
    if project["owner_id"] != user["_id"]:
        raise forbidden("Only the project creator can view candidate recommendations")
    with anyio.fail_after(timeout_s):
        request, docs = await build_request(db, store, project)
        result = await anyio.to_thread.run_sync(rank_candidates, request, INITIAL_WEIGHTS)
    spec = request.project
    page = result.ranked[offset: offset + limit]
    users = await users_by_id(db, [ObjectId(r.candidate_id) for r in page])
    pending = {
        str(i["candidate_id"]): i["status"]
        async for i in db.invitations.find({"project_id": project["_id"], "status": "pending"}, {"candidate_id": 1, "status": 1})
    }
    excluded = Counter(r.code.value for d in result.excluded for r in d.failures)
    return {
        "project_id": project_id,
        "status": "closed" if project["status"] != "open" else result.status,
        "open_positions": result.open_positions,
        "team_size": len(request.team),
        "team_coverage": coverage_out(result, spec),
        "team_slots": None if result.team_slots.slots is None else len(result.team_slots.slots),
        "configured_weights": result.configured_weights,
        "active_weights": result.active_weights,
        "feature_labels": FEATURE_LABELS,
        "omitted_features": result.omitted_features,
        "weights_renormalized": result.weights_renormalized,
        "warnings": result.warnings,
        "encoder": store.encoder.model_id,
        "pool": {"considered": len(request.candidates), "eligible": len(result.ranked),
                 "excluded": len(result.excluded), "excluded_by_reason": dict(excluded)},
        "total": len(result.ranked),
        "limit": limit,
        "offset": offset,
        "candidates": [{
            "rank": r.rank,
            "score": r.score,
            "features": {k: _feature(v) for k, v in r.features.items()},
            "added_coverage": r.gain,
            "coverage_after": r.coverage_after,
            "explanation": r.explanation,
            "explanation_text": r.explanation_text,
            "invitation_status": pending.get(r.candidate_id),
            "profile": public_profile(docs[r.candidate_id], users.get(ObjectId(r.candidate_id))
                                      or {"display_name": "Unknown", "handle": None}),
        } for r in page],
        "notice": "Scores rank candidates for this request only. They are not probabilities of team success; "
                  "proficiency is self-reported.",
    }


async def team_coverage(db, user: dict, project_id: str) -> dict[str, Any]:
    """Coverage of the current team; visible to anyone who can see the project."""
    project = await get_project_for(db, project_id, user)
    member_ids = [m["user_id"] for m in project["members"]]
    team_docs = {d["_id"]: d async for d in db.profiles.find({"_id": {"$in": member_ids}})}
    team = tuple(to_domain(team_docs.get(uid) or empty_profile(uid)) for uid in member_ids)
    spec = to_spec(project)
    result = rank_candidates(RecommendationRequest(spec, team, (), {}), INITIAL_WEIGHTS)
    return coverage_out(result, spec)
