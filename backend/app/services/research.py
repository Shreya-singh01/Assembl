"""Research workflow on top of MongoDB: scenarios, judging, evaluation runs.

* Scenarios are stored as their raw JSON plus provenance flags.
* Human ratings are collected through anonymised packets (raters never see
  candidate ids, names, method names or scores) and stored in ``judgments``.
  When a scenario has human ratings, evaluation uses only those and marks the
  scenario's judgments as ``human``; simulated ratings are never mixed in.
* Ratings are used only offline by the evaluation pipeline. They never change
  deployed recommendations.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import anyio

from app.core.errors import bad_request, conflict, not_found
from app.research.methods import METHOD_NAMES, eligible_pool, run_methods
from app.research.pooling import build_pool, judging_packet
from app.research.report import render_markdown
from app.research.runner import EvalConfig, Evaluator
from app.research.scenario import RATING_LABELS, scenario_from_dict
from app.research.synthetic import generate
from app.services.auth import now

log = logging.getLogger(__name__)
_background: set[asyncio.Task] = set()  # keep references so running jobs are not garbage-collected


async def status(db) -> dict[str, Any]:
    scen = [s async for s in db.research_scenarios.find({}, {"provenance": 1, "judgment_provenance": 1, "packet": 1})]
    human_ids = await db.judgments.distinct("scenario_id")
    runs = [r async for r in db.evaluation_runs.find({}, {"report": 0, "markdown": 0}).sort("created_at", -1).limit(1)]
    real = [s for s in scen if s["provenance"] == "real"]
    real_judged = [s for s in real if s["_id"] in human_ids]
    return {
        "methods_implemented": METHOD_NAMES,
        "scenarios": {"total": len(scen), "real": len(real), "synthetic": len(scen) - len(real),
                      "with_judging_packets": sum(1 for s in scen if s.get("packet")),
                      "with_human_judgments": len(human_ids), "real_with_human_judgments": len(real_judged),
                      "with_simulated_judgments": sum(1 for s in scen if s.get("judgment_provenance") == "simulated")},
        "target_scenarios": 30,
        "human_judgments": await db.judgments.count_documents({}),
        "runs_completed": await db.evaluation_runs.count_documents({"state": "complete"}),
        "latest_run": runs[0] if runs else None,
        "evaluation_status": "measured" if any(r.get("is_research_evidence") for r in runs) else "pending",
        "open_tasks": [t for t, todo in [
            ("Collect consent-based real scenarios (target: 30)", len(real) < 30),
            ("Collect at least three independent human ratings per real scenario", len(real_judged) < len(real) or not real),
            ("Run the evaluation on real, human-judged scenarios", not any(r.get("is_research_evidence") for r in runs)),
        ] if todo],
    }


async def import_scenarios(db, items: list[dict], admin: dict) -> list[str]:
    ids = []
    for d in items:
        try:
            s = scenario_from_dict(d)
        except (ValueError, KeyError, TypeError) as exc:
            raise bad_request(f"invalid scenario {d.get('scenario_id', '?')}: {exc}") from None
        await db.research_scenarios.replace_one(
            {"_id": s.scenario_id},
            {"_id": s.scenario_id, "data": d, "provenance": s.provenance, "judgment_provenance": s.judgment_provenance,
             "imported_at": now(), "imported_by": admin["_id"]},
            upsert=True)
        ids.append(s.scenario_id)
    return ids


async def import_synthetic(db, admin: dict, seed: int) -> list[str]:
    return await import_scenarios(db, generate(seed=seed), admin)


async def _load(db, scenario_ids: list[str] | None = None):
    flt = {"_id": {"$in": scenario_ids}} if scenario_ids else {}
    out = []
    async for doc in db.research_scenarios.find(flt):
        data = dict(doc["data"])
        human = [j async for j in db.judgments.find({"scenario_id": doc["_id"]})]
        if human:
            data["judgments"] = [{"rater_id": str(j["rater_id"]), "candidate_id": j["candidate_id"], "rating": j["rating"]}
                                 for j in human]
            data["judgment_provenance"] = "human"
        out.append(scenario_from_dict(data))
    return out


async def build_packet(db, encoder, scenario_id: str, seed: int = 0, extra: int = 3) -> dict:
    scenarios = await _load(db, [scenario_id])
    if not scenarios:
        raise not_found("Scenario")
    s = scenarios[0]

    def work():
        ev = Evaluator(encoder)
        pool, _ = eligible_pool(s)
        ranks = run_methods(s, pool, ev.semantic(s, pool))
        ids = build_pool(ranks, [c.user_id for c in pool], top_n=10, extra=extra, seed=seed)
        return judging_packet(s, ids)

    packet = await anyio.to_thread.run_sync(work)
    key = packet.pop("_label_to_candidate")
    await db.research_scenarios.update_one({"_id": scenario_id}, {"$set": {"packet": packet, "packet_key": key}})
    return packet


async def rater_tasks(db, rater: dict) -> list[dict]:
    done = set(await db.judgments.distinct("scenario_id", {"rater_id": rater["_id"]}))
    tasks = []
    async for s in db.research_scenarios.find({"packet": {"$exists": True}}, {"packet": 1, "provenance": 1}):
        tasks.append({"scenario_id": s["_id"], "provenance": s["provenance"], "title": s["packet"]["project"]["title"],
                      "candidates": len(s["packet"]["candidates"]), "completed": s["_id"] in done})
    return sorted(tasks, key=lambda t: (t["completed"], t["scenario_id"]))


async def rater_packet(db, rater: dict, scenario_id: str) -> dict:
    s = await db.research_scenarios.find_one({"_id": scenario_id, "packet": {"$exists": True}}, {"packet": 1})
    if not s:
        raise not_found("Judging task")
    packet = dict(s["packet"])
    cands = list(packet["candidates"])
    random.Random(f"{scenario_id}:{rater['_id']}").shuffle(cands)  # random order per rater
    packet["candidates"] = cands
    return packet


async def submit_ratings(db, rater: dict, scenario_id: str, ratings: dict[str, int]) -> int:
    s = await db.research_scenarios.find_one({"_id": scenario_id}, {"packet_key": 1})
    if not s or not s.get("packet_key"):
        raise not_found("Judging task")
    key: dict[str, str] = s["packet_key"]
    unknown = set(ratings) - set(key)
    if unknown:
        raise bad_request(f"unknown candidate labels: {sorted(unknown)}")
    if set(key) - set(ratings):
        raise bad_request("please rate every candidate in the packet")
    for label, rating in ratings.items():
        if rating not in RATING_LABELS:
            raise bad_request("ratings must be 0, 1, 2 or 3")
    if await db.judgments.find_one({"scenario_id": scenario_id, "rater_id": rater["_id"]}):
        raise conflict("You have already rated this scenario")
    await db.judgments.insert_many([
        {"scenario_id": scenario_id, "candidate_id": key[label], "rater_id": rater["_id"], "rating": rating,
         "created_at": now()} for label, rating in ratings.items()])
    return len(ratings)


async def start_evaluation(db, encoder, admin: dict, config: EvalConfig) -> str:
    scenarios = await _load(db)
    if not scenarios:
        raise bad_request("No scenarios to evaluate; import scenarios first")
    run_id = f"pending-{now().strftime('%Y%m%dT%H%M%S%f')}"
    await db.evaluation_runs.insert_one({"_id": run_id, "state": "running", "created_at": now(), "started_by": admin["_id"]})

    async def job():
        try:
            report = await anyio.to_thread.run_sync(lambda: Evaluator(encoder).evaluate(scenarios, config))
            await db.evaluation_runs.update_one({"_id": run_id}, {"$set": {
                "state": "complete", "run_id": report["run_id"], "status": report["status"],
                "is_research_evidence": report["is_research_evidence"], "warnings": report["warnings"],
                "dataset": report["dataset"], "report": report, "markdown": render_markdown(report),
                "finished_at": now()}})
        except Exception as exc:  # noqa: BLE001 - surfaced through the run record
            log.exception("evaluation failed")
            await db.evaluation_runs.update_one({"_id": run_id}, {"$set": {"state": "failed",
                                                                            "error": exc.__class__.__name__}})

    task = asyncio.get_running_loop().create_task(job())
    _background.add(task)
    task.add_done_callback(_background.discard)
    return run_id
