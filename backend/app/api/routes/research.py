"""/api/v1/research - evaluation status, runs, scenarios and rating tasks.

Status and runs are readable by any signed-in user (transparency); importing
scenarios and starting runs requires an administrator; rating requires the
rater role. Ratings never influence live recommendations.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request, status
from pydantic import BaseModel, Field

from app.api.deps import AdminUser, CurrentUser, Db, RaterUser
from app.core.errors import not_found, oid
from app.core.serialize import plain
from app.research.runner import EvalConfig
from app.services import research as svc

router = APIRouter(prefix="/research", tags=["research"])


class EvaluateIn(BaseModel):
    seed: int = 13
    grid_step: float = Field(0.1, gt=0, le=0.5)
    dev_fraction: float = Field(0.5, gt=0, lt=1)
    calibrate: bool = True
    robustness: bool = True


class RatingsIn(BaseModel):
    ratings: dict[str, int] = Field(description="candidate label (C01, ...) -> rating 0-3")


@router.get("/status")
async def research_status(user: CurrentUser, db: Db):
    return plain(await svc.status(db))


@router.get("/runs")
async def list_runs(user: CurrentUser, db: Db):
    return plain([r async for r in db.evaluation_runs.find({}, {"report": 0, "markdown": 0}).sort("created_at", -1).limit(50)])


@router.get("/runs/{run_id}")
async def get_run(run_id: str, user: CurrentUser, db: Db):
    run = await db.evaluation_runs.find_one({"_id": run_id[:80]})
    if not run:
        raise not_found("Run")
    return plain(run)


@router.post("/evaluate", status_code=status.HTTP_202_ACCEPTED)
async def evaluate(data: EvaluateIn, request: Request, admin: AdminUser, db: Db):
    cfg = EvalConfig(seed=data.seed, grid_step=data.grid_step, dev_fraction=data.dev_fraction,
                     calibrate=data.calibrate, run_robustness=data.robustness)
    run_id = await svc.start_evaluation(db, request.app.state.encoder, admin, cfg)
    return {"id": run_id, "state": "running"}


@router.get("/scenarios")
async def list_scenarios(admin: AdminUser, db: Db):
    return plain([{"id": s["_id"], "provenance": s["provenance"], "judgment_provenance": s["judgment_provenance"],
                   "has_packet": "packet" in s, "imported_at": s.get("imported_at")}
                  async for s in db.research_scenarios.find({}, {"data": 0, "packet_key": 0})])


@router.post("/scenarios/import", status_code=201)
async def import_scenarios(admin: AdminUser, db: Db, scenarios: list[dict[str, Any]] = Body(..., max_length=200)):
    return {"imported": await svc.import_scenarios(db, scenarios, admin)}


@router.post("/scenarios/synthetic", status_code=201)
async def import_synthetic(admin: AdminUser, db: Db, seed: int = 42):
    """Load the clearly labelled synthetic scenario set (for demonstrations)."""
    return {"imported": await svc.import_synthetic(db, admin, seed)}


@router.post("/scenarios/{scenario_id}/packet")
async def build_packet(scenario_id: str, request: Request, admin: AdminUser, db: Db):
    """Pool top-10 candidates from every method plus random extras into an anonymised rating packet."""
    packet = await svc.build_packet(db, request.app.state.encoder, scenario_id)
    return {"scenario_id": scenario_id, "candidates": len(packet["candidates"])}


@router.post("/raters/{user_id}", status_code=204)
async def grant_rater(user_id: str, admin: AdminUser, db: Db):
    res = await db.users.update_one({"_id": oid(user_id, "User"), "role": "student"}, {"$set": {"role": "rater"}})
    if res.matched_count == 0 and not await db.users.find_one({"_id": oid(user_id, "User")}):
        raise not_found("User")


@router.get("/judging/tasks")
async def judging_tasks(rater: RaterUser, db: Db):
    return await svc.rater_tasks(db, rater)


@router.get("/judging/{scenario_id}")
async def judging_packet(scenario_id: str, rater: RaterUser, db: Db):
    return await svc.rater_packet(db, rater, scenario_id)


@router.post("/judging/{scenario_id}", status_code=201)
async def submit_ratings(scenario_id: str, data: RatingsIn, rater: RaterUser, db: Db):
    return {"stored": await svc.submit_ratings(db, rater, scenario_id, data.ratings)}
