"""Load synthetic platform data (users, profiles, projects, teams, invitations,
conversations, research scenarios) into MongoDB through the real services.

Everything goes through the same code paths as real users (profile
normalisation, project validation, concurrency-safe invite/accept, messaging),
so the data is consistent with what the app itself would produce.

After loading, every project is ranked by the real engine and checked against
the behaviour its case is meant to trigger (e.g. a full team must return
``team_full``; a team covering every requirement must drop ``f_gap``).
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import anyio
from bson import ObjectId
from fastapi import HTTPException
from pymongo import UpdateOne

from app.core.security import hash_password
from app.domain.engine import rank_candidates
from app.domain.scoring import INITIAL_WEIGHTS
from app.research.synthetic import BASE_PROJECTS
from app.research.synthetic import generate as generate_scenarios
from app.schemas.profiles import ProfileIn
from app.schemas.projects import ProjectIn
from app.services import messaging, teams
from app.services import research as research_svc
from app.services.auth import now
from app.services.embedding_store import EmbeddingStore
from app.services.profiles import save_profile
from app.services.projects import create_project, expire_pending_invitations
from app.services.recommendations import build_request
from app.websocket.notifier import Notifier

from . import DEMO_DOMAIN, DEMO_PASSWORD
from .people import StudentPlan, make_students

log = logging.getLogger(__name__)
EVENT_KEY = "smart-india-hackathon-2026"
TEAM_NAMES = ["Nova", "Orbit", "Pixel", "Quark", "Lambda", "Vertex", "Echo", "Zenith", "Delta", "Helix",
              "Prism", "Atlas", "Cipher", "Comet", "Nimbus", "Spark", "Vector", "Fusion", "Pulse", "Tangent"]
OPPORTUNITY = {"P01": "hackathon", "P02": "hackathon", "P03": "startup", "P04": "academic", "P05": "research",
               "P06": "academic", "P07": "competition", "P08": "academic", "P09": "startup", "P10": "competition",
               "P11": "research", "P12": "other"}

# One entry per project. Each case is chosen to trigger a specific rule or state.
CASES: list[dict[str, Any]] = [
    {"name": "standard", "team": 2},
    {"name": "sync_all_members", "team": 2, "set": {"synchronous": True, "min_shared_slots": 2}, "flag": "shared_slots"},
    {"name": "sync_majority_policy", "team": 3, "set": {"synchronous": True, "min_shared_slots": 2, "availability_policy": "majority"}, "flag": "stated_slots"},
    {"name": "sync_mandatory_availability", "team": 2, "set": {"synchronous": True, "min_shared_slots": 2, "availability_mandatory": True}, "flag": "shared_slots"},
    {"name": "mandatory_skill_exclude_unknown", "team": 2, "flag": "mandatory_first"},
    {"name": "mandatory_skill_include_unknown", "team": 2, "flag": "mandatory_first", "set": {"unverifiable_policy": "include"}},
    {"name": "allowed_years", "team": 1, "set": {"allowed_years": [2, 3]}},
    {"name": "role_mandatory", "team": 2, "set": {"role_mandatory": True}},
    {"name": "event_team_a", "team": 2, "set": {"event_key": EVENT_KEY}},
    {"name": "event_team_b", "team": 1, "set": {"event_key": EVENT_KEY}},
    {"name": "event_team_c", "team": 2, "set": {"event_key": EVENT_KEY}},
    {"name": "full_team", "team": 3, "flag": "full"},
    {"name": "requirements_already_covered", "team": 2, "flag": "covered"},
    {"name": "single_member", "team": 1},
    {"name": "no_vacant_roles", "team": 2, "set": {"vacant_roles": []}},
    {"name": "no_hours_or_mode", "team": 2, "set": {"weekly_hours": None, "work_mode": None}},
    {"name": "private_project", "team": 2, "set": {"visibility": "private"}},
    {"name": "closed_project", "team": 2, "flag": "closed"},
    {"name": "sync_no_member_availability", "team": 2, "set": {"synchronous": True, "min_shared_slots": 2}, "flag": "no_slots"},
    {"name": "sync_no_common_slot", "team": 2, "set": {"synchronous": True, "min_shared_slots": 1}, "flag": "disjoint_slots"},
    {"name": "many_requirements", "team": 2, "flag": "many_reqs"},
    {"name": "unrecognised_requirement", "team": 1, "flag": "odd_req"},
    {"name": "large_team", "team": 4, "target": 6},
    {"name": "joined_by_request", "team": 3, "flag": "via_request"},
]
FILLER = ["standard", "single_member", "sync_all_members", "large_team", "joined_by_request", "standard"]

MESSAGES = [
    "Hey! I saw your profile — would you be up for joining our team?",
    "Sure, what's the project timeline looking like?",
    "We're aiming to have a working prototype in two weeks.",
    "Sounds good. I can take the backend if that's still open.",
    "Can we meet on Wednesday evening to split the work?",
    "I pushed the first version of the API, take a look when you can.",
    "The Figma screens are ready for review.",
    "Let's do a quick call before the submission deadline.",
    "I'll handle the presentation slides.",
    "Great work today, see you all tomorrow!",
    "Did anyone set up the database yet?",
    "I can do weekends this month, weekdays are tough with labs.",
]


@dataclass
class ProjectPlan:
    index: int
    case: dict[str, Any]
    theme: dict[str, Any]
    owner: int
    members: list[tuple[int, str | None, str]]  # (student, role offered, "invite"|"request")
    payload: dict[str, Any]
    extras: list[tuple[str, int]] = field(default_factory=list)  # (action, student)
    closed: bool = False
    expected: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Planning (pure, deterministic)
# ---------------------------------------------------------------------------

def _reqs(theme: dict) -> list[dict]:
    return [{"skill": s, "importance": a, "desired_proficiency": r, "mandatory": False} for s, a, r in theme["requirements"]]


def plan_projects(students: list[StudentPlan], n_projects: int, seed: int) -> list[ProjectPlan]:
    rng = random.Random(seed)
    teams_of = {s.index: 0 for s in students}
    event_members: set[int] = set()
    cases = [*CASES, *[next(c for c in CASES if c["name"] == FILLER[i % len(FILLER)]) for i in range(max(0, n_projects - len(CASES)))]]
    cases = cases[:n_projects]
    plans: list[ProjectPlan] = []

    def usable(s: StudentPlan, *, max_teams: int = 2) -> bool:
        return s.visible and bool(s.canonical_skills) and teams_of[s.index] < max_teams and s.index not in event_members

    def pick(pred, k: int, exclude: set[int]) -> list[int]:
        pool = [s.index for s in students if s.index not in exclude and pred(students[s.index])]
        rng.shuffle(pool)
        return pool[:k]

    for k, case in enumerate(cases):
        theme = BASE_PROJECTS[k % len(BASE_PROJECTS)]
        flag = case.get("flag")
        size = case["team"]
        arch = set(theme["archetypes"])
        in_theme = lambda s: s.archetype in arch  # noqa: E731

        # --- owner -----------------------------------------------------------
        if k == 0:
            owner = 0
        else:
            if flag == "no_slots":
                preferred = pick(lambda s: usable(s) and s.availability is None, 1, set())
            elif flag in ("shared_slots", "stated_slots", "disjoint_slots"):
                preferred = pick(lambda s: usable(s) and bool(s.availability) and len(s.availability) >= 4, 1, set())
            else:
                preferred = pick(lambda s: usable(s) and in_theme(s), 1, set())
            fallback = preferred or pick(usable, 1, set()) or pick(lambda s: s.visible and bool(s.canonical_skills), 1, set())
            if not fallback:
                break  # not enough students for more projects
            owner = fallback[0]
        team = [owner]

        # --- members ---------------------------------------------------------
        for _ in range(size - 1):
            ex = set(team)
            if flag == "no_slots":
                cand = pick(lambda s: usable(s) and s.availability is None, 1, ex)
            elif flag == "shared_slots":
                base = set.intersection(*[students[t].availability for t in team])
                cand = pick(lambda s: usable(s) and bool(s.availability) and len(s.availability & base) >= 2, 1, ex)
            elif flag == "stated_slots":
                cand = pick(lambda s: usable(s) and bool(s.availability), 1, ex)
            elif flag == "disjoint_slots":
                base = set().union(*[students[t].availability for t in team])
                cand = pick(lambda s: usable(s) and bool(s.availability) and not (s.availability & base), 1, ex)
            else:
                cand = pick(lambda s: usable(s) and not in_theme(s), 1, ex) if rng.random() < 0.6 else []
                cand = cand or pick(usable, 1, ex)
            if cand:
                team.append(cand[0])
        for t in team:
            teams_of[t] += 1
            if case.get("set", {}).get("event_key"):
                event_members.add(t)

        # --- requirements ----------------------------------------------------
        reqs = _reqs(theme)
        if flag == "covered":
            have: dict[str, int] = {}
            for t in team:
                for sk, lv in students[t].canonical_skills.items():
                    have[sk] = max(have.get(sk, 0), lv)
            top = sorted(have.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
            reqs = [{"skill": sk, "importance": rng.randint(1, 3), "desired_proficiency": min(lv, 3), "mandatory": False}
                    for sk, lv in top]
        elif flag == "many_reqs":
            extra = [r for o in BASE_PROJECTS if o is not theme for r in _reqs(o)]
            names = {r["skill"] for r in reqs}
            for r in extra:
                if len(reqs) >= 10:
                    break
                if r["skill"] not in names:
                    reqs.append(r)
                    names.add(r["skill"])
        elif flag == "odd_req":
            reqs.append({"skill": rng.choice(["LaTeX", "Godot", "Blender"]), "importance": 1, "desired_proficiency": 2, "mandatory": False})
        if flag == "mandatory_first":
            reqs[0]["mandatory"] = True
            reqs[0]["desired_proficiency"] = 2

        owner_role = (students[owner].primary_roles or [None])[0]
        vacant = [r for r in theme["roles"] if not owner_role or r.lower() != owner_role.lower()]
        payload: dict[str, Any] = {
            "title": f"{theme['title']} · Team {TEAM_NAMES[k % len(TEAM_NAMES)]}",
            "description": theme["description"] + " (Synthetic demo project.)",
            "opportunity_type": OPPORTUNITY[theme["id"]],
            "event_key": None,
            "requirements": reqs,
            "target_size": case.get("target") or (len(team) if flag == "full" else min(12, len(team) + rng.randint(1, 3))),
            "creator_role": owner_role,
            "vacant_roles": vacant,
            "allowed_years": None,
            "role_mandatory": False,
            "synchronous": False,
            "min_shared_slots": 0,
            "availability_policy": "all",
            "availability_mandatory": False,
            "weekly_hours": rng.choice([6, 8, 10, 12, 15]),
            "work_mode": rng.choice(["online", "offline", "hybrid"]),
            "unverifiable_policy": "exclude",
            "visibility": "public",
        }
        payload.update(case.get("set", {}))
        if payload["target_size"] < 2:
            payload["target_size"] = 2

        # --- how members join ----------------------------------------------
        members: list[tuple[int, str | None, str]] = []
        open_roles = list(payload["vacant_roles"])
        for t in team[1:]:
            role = next((r for r in open_roles if r.lower() in {p.lower() for p in students[t].primary_roles}), None)
            if role:
                open_roles.remove(role)
            mode = "request" if flag == "via_request" or (payload["visibility"] == "public" and rng.random() < 0.15) else "invite"
            members.append((t, role, mode))

        # --- other invitation traffic -----------------------------------------
        extras: list[tuple[str, int]] = []
        outsiders = pick(lambda s: s.visible and bool(s.canonical_skills) and s.index not in event_members, 6, set(team))
        if flag == "full":
            extras = [("invite_pending_then_expires", o) for o in outsiders[:2]]
        elif flag != "closed" and outsiders:
            actions = ["invite_pending", "invite_declined", "invite_cancelled"]
            if payload["visibility"] == "public":
                actions += ["request_pending", "request_declined"]
            chosen = rng.sample(actions, rng.randint(1, min(4, len(actions))))
            extras = list(zip(chosen, outsiders))

        expected = _expectations(case["name"], len(team))
        plans.append(ProjectPlan(k, case, theme, owner, members, payload, extras, flag == "closed", expected))
    return plans


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

async def _chunked(coros, size: int = 20):
    out = []
    for i in range(0, len(coros), size):
        out.extend(await asyncio.gather(*coros[i:i + size]))
    return out


async def demo_present(db) -> bool:
    return bool(await db.users.find_one({"email": {"$regex": f"@{re.escape(DEMO_DOMAIN)}$"}}, {"_id": 1}))


async def clear(db) -> dict[str, int]:
    """Remove every synthetic record (and only those)."""
    users = [u["_id"] async for u in db.users.find({"email": {"$regex": f"@{re.escape(DEMO_DOMAIN)}$"}}, {"_id": 1})]
    projects = [p["_id"] async for p in db.projects.find({"$or": [{"demo": True}, {"owner_id": {"$in": users}}]}, {"_id": 1})]
    convs = [c["_id"] async for c in db.conversations.find(
        {"$or": [{"participant_ids": {"$in": users}}, {"project_id": {"$in": projects}}]}, {"_id": 1})]
    synthetic_scen = [s["_id"] async for s in db.research_scenarios.find({"provenance": "synthetic"}, {"_id": 1})]
    out = {
        "messages": (await db.messages.delete_many({"$or": [{"conversation_id": {"$in": convs}}, {"sender_id": {"$in": users}}]})).deleted_count,
        "conversations": (await db.conversations.delete_many({"_id": {"$in": convs}})).deleted_count,
        "invitations": (await db.invitations.delete_many({"$or": [{"project_id": {"$in": projects}}, {"from_user": {"$in": users}}, {"candidate_id": {"$in": users}}]})).deleted_count,
        "projects": (await db.projects.delete_many({"_id": {"$in": projects}})).deleted_count,
        "embeddings": (await db.embeddings.delete_many({"user_id": {"$in": users}})).deleted_count,
        "profiles": (await db.profiles.delete_many({"_id": {"$in": users}})).deleted_count,
        "sessions": (await db.sessions.delete_many({"user_id": {"$in": users}})).deleted_count,
        "judgments": (await db.judgments.delete_many({"$or": [{"rater_id": {"$in": users}}, {"scenario_id": {"$in": synthetic_scen}}]})).deleted_count,
        "research_scenarios": (await db.research_scenarios.delete_many({"_id": {"$in": synthetic_scen}})).deleted_count,
        "evaluation_runs": (await db.evaluation_runs.delete_many({"synthetic": True})).deleted_count,
        "users": (await db.users.delete_many({"_id": {"$in": users}})).deleted_count,
    }
    await db.synthetic_meta.delete_many({})
    return out


async def _create_users(db, students: list[StudentPlan]) -> dict[int, dict]:
    pw = hash_password(DEMO_PASSWORD)
    rng = random.Random(5)
    docs = []
    for s in students:
        docs.append({
            "_id": ObjectId(), "email": f"{s.handle}@{DEMO_DOMAIN}", "password_hash": pw,
            "display_name": f"{s.first} {s.last} (demo)", "handle": s.handle, "handle_key": s.handle.lower(),
            "role": "student", "created_at": now() - timedelta(days=rng.uniform(20, 90)),
            "consent": {"terms_accepted_at": now(), "research_participation": rng.random() < 0.6},
        })
    staff = [("admin_demo", "Admin (demo)", "admin"), ("rater_demo1", "Rater One (demo)", "rater"),
             ("rater_demo2", "Rater Two (demo)", "rater"), ("rater_demo3", "Rater Three (demo)", "rater")]
    for handle, name, role in staff:
        docs.append({"_id": ObjectId(), "email": f"{handle}@{DEMO_DOMAIN}", "password_hash": pw, "display_name": name,
                     "handle": handle, "handle_key": handle, "role": role, "created_at": now() - timedelta(days=30),
                     "consent": {"terms_accepted_at": now(), "research_participation": False}})
    await db.users.insert_many(docs)
    return {i: d for i, d in enumerate(docs[:len(students)])}


async def _try(coro):
    try:
        return await coro
    except HTTPException as exc:
        log.info("skipped synthetic action: %s", exc.detail)
        return None


async def _execute_project(db, plan: ProjectPlan, users: dict[int, dict], stats: dict) -> dict | None:
    notifier = Notifier(None)
    owner = users[plan.owner]
    project = await create_project(db, owner, ProjectIn(**plan.payload))
    pid = str(project["_id"])
    await db.projects.update_one({"_id": project["_id"]}, {"$set": {"demo": True, "synthetic_case": plan.case["name"]}})
    await messaging.sync_team_conversation(db, project)

    pending_member_invites = []
    for student, role, mode in plan.members:
        u = users[student]
        if mode == "request":
            inv = await _try(teams.request_to_join(db, notifier, u, pid, role, "I'd love to help with this!"))
            if inv:
                pending_member_invites.append((inv, owner))
        else:
            inv = await _try(teams.invite(db, notifier, owner, pid, str(u["_id"]), role, "Your profile fits what we need."))
            if inv:
                pending_member_invites.append((inv, u))
    for action, student in plan.extras:  # extra traffic is created before the team fills up
        u = users[student]
        if action in ("invite_pending", "invite_pending_then_expires"):
            await _try(teams.invite(db, notifier, owner, pid, str(u["_id"]), None, "Interested in joining us?"))
        elif action == "invite_declined":
            inv = await _try(teams.invite(db, notifier, owner, pid, str(u["_id"]), None, "Would you like to join?"))
            if inv:
                await _try(teams.respond(db, notifier, u, str(inv["_id"]), "decline"))
        elif action == "invite_cancelled":
            inv = await _try(teams.invite(db, notifier, owner, pid, str(u["_id"]), None, "Join us?"))
            if inv:
                await _try(teams.respond(db, notifier, owner, str(inv["_id"]), "cancel"))
        elif action == "request_pending":
            await _try(teams.request_to_join(db, notifier, u, pid, None, "Can I join your team?"))
        elif action == "request_declined":
            inv = await _try(teams.request_to_join(db, notifier, u, pid, None, "Room for one more?"))
            if inv:
                await _try(teams.respond(db, notifier, owner, str(inv["_id"]), "decline"))
    for inv, responder in pending_member_invites:
        await _try(teams.respond(db, notifier, responder, str(inv["_id"]), "accept"))
    if plan.closed:
        await db.projects.update_one({"_id": project["_id"]}, {"$set": {"status": "closed"}, "$inc": {"version": 1},
                                                               "$push": {"history": {"at": now(), "type": "edited", "user_id": owner["_id"], "by": owner["_id"]}}})
        await expire_pending_invitations(db, project["_id"], "project_closed")
    project = await db.projects.find_one({"_id": project["_id"]})
    stats["projects"] += 1
    return project


async def _team_chat(db, project: dict, users_by_id: dict, rng: random.Random) -> None:
    members = [users_by_id[m["user_id"]] for m in project["members"] if m["user_id"] in users_by_id]
    if len(members) < 2:
        return
    conv = await db.conversations.find_one({"project_id": project["_id"], "kind": "team"})
    for i in range(rng.randint(2, 6)):
        await _try(messaging.send_message(db, members[i % len(members)], str(conv["_id"]), rng.choice(MESSAGES), None, 4000))


async def _direct_chats(db, students: list[StudentPlan], users: dict[int, dict], n: int, rng: random.Random) -> int:
    made = 0
    visible = [s.index for s in students if s.visible]
    for _ in range(n):
        a, b = rng.sample(visible, 2)
        conv = await _try(messaging.get_or_create_direct(db, users[a], str(users[b]["_id"])))
        if not conv:
            continue
        for i in range(rng.randint(1, 6)):
            sender = users[a] if i % 2 == 0 else users[b]
            await _try(messaging.send_message(db, sender, str(conv["_id"]), MESSAGES[(i + made) % len(MESSAGES)], None, 4000))
        made += 1
    return made


async def _backdate(db, users_by_id: dict, rng: random.Random) -> None:
    """Spread timestamps over the past weeks so the data looks lived-in."""
    projects = [p async for p in db.projects.find({"demo": True}, {"_id": 1})]
    ops = [UpdateOne({"_id": p["_id"]}, {"$set": {"created_at": now() - timedelta(days=rng.uniform(3, 45))}}) for p in projects]
    if ops:
        await db.projects.bulk_write(ops)
    convs = [c async for c in db.conversations.find({"participant_ids": {"$in": list(users_by_id)}})]
    msg_ops, conv_ops = [], []
    for c in convs:
        msgs = [m async for m in db.messages.find({"conversation_id": c["_id"]}).sort("_id", 1)]
        if not msgs:
            continue
        t = now() - timedelta(days=rng.uniform(1, 14))
        for m in msgs:
            t += timedelta(minutes=rng.uniform(2, 600))
            t = min(t, now())
            msg_ops.append(UpdateOne({"_id": m["_id"]}, {"$set": {"created_at": t}}))
        reads = {str(p): t for p in c["participant_ids"] if rng.random() < 0.6}
        conv_ops.append(UpdateOne({"_id": c["_id"]}, {"$set": {"last_message_at": t, "reads": reads}}))
    if msg_ops:
        await db.messages.bulk_write(msg_ops)
    if conv_ops:
        await db.conversations.bulk_write(conv_ops)


async def verify(db, encoder) -> list[dict]:
    """Rank every synthetic project with the real engine and check that each
    case triggers the behaviour it was built for. Also warms the embedding cache."""
    store = EmbeddingStore(db, encoder)
    results = []
    async for p in db.projects.find({"demo": True}).sort("_id", 1):
        request, _ = await build_request(db, store, p)
        res = await anyio.to_thread.run_sync(rank_candidates, request, INITIAL_WEIGHTS)
        reasons: dict[str, int] = {}
        for d in res.excluded:
            for r in d.failures:
                reasons[r.code.value] = reasons.get(r.code.value, 0) + 1
        case = p.get("synthetic_case", "")
        exp = _expectations(case, len(p["members"]))
        checks = []
        if "status" in exp:
            checks.append(("status == " + exp["status"], res.status == exp["status"]))
        if "omitted" in exp:
            checks.append((f"'{exp['omitted']}' omitted", exp["omitted"] in res.omitted_features))
        if "warning" in exp:
            checks.append(("warning: " + exp["warning"], any(exp["warning"] in w for w in res.warnings)))
        if "excluded_reason" in exp:
            checks.append(("excludes " + exp["excluded_reason"], reasons.get(exp["excluded_reason"], 0) > 0))
        if "excluded_reason_any" in exp:
            checks.append(("excludes " + "/".join(exp["excluded_reason_any"]), any(reasons.get(r, 0) for r in exp["excluded_reason_any"])))
        if exp.get("unverified_flagged"):
            checks.append(("unverified candidates ranked with a flag", any(r.explanation["unverified_rules"] for r in res.ranked)))
        results.append({
            "project": p["title"], "case": case, "members": len(p["members"]), "status": res.status,
            "eligible": len(res.ranked), "excluded": len(res.excluded), "excluded_by_reason": reasons,
            "omitted": sorted(res.omitted_features), "warnings": res.warnings,
            "checks": [{"check": c, "passed": ok} for c, ok in checks],
        })
    return results


def _expectations(case: str, members: int) -> dict:
    exp: dict[str, Any] = {}
    if case == "full_team":
        exp["status"] = "team_full"
    elif case == "requirements_already_covered":
        exp["omitted"] = "gap"
    elif case == "no_vacant_roles":
        exp["omitted"] = "role"
    elif case == "no_hours_or_mode":
        exp["omitted"] = "work"
    elif case == "sync_no_member_availability":
        exp.update(omitted="avail", warning="No current member has stated weekly availability")
    elif case == "sync_no_common_slot" and members > 1:
        exp["warning"] = "share no common weekly slot"
    elif case == "mandatory_skill_exclude_unknown":
        exp["excluded_reason"] = "MANDATORY_SKILL_UNVERIFIED"
    elif case == "mandatory_skill_include_unknown":
        exp["unverified_flagged"] = True
    elif case == "allowed_years":
        exp["excluded_reason"] = "YEAR_NOT_ALLOWED"
    elif case == "role_mandatory":
        exp["excluded_reason"] = "ROLE_NOT_MATCHED"
    elif case in ("event_team_a", "event_team_b", "event_team_c"):
        exp["excluded_reason"] = "COMMITTED_TO_EVENT_TEAM"
    elif case == "sync_mandatory_availability":
        exp["excluded_reason_any"] = ["AVAILABILITY_NOT_MET", "AVAILABILITY_UNVERIFIED"]
    return exp


async def load(db, *, students: int = 300, projects: int = 40, seed: int = 11, direct_chats: int = 40,
               research: bool = True, encoder=None, packets: int = 3) -> dict:
    rng = random.Random(seed)
    stats: dict[str, Any] = {"projects": 0}
    plans_students = make_students(students, seed)
    users = await _create_users(db, plans_students)
    users_by_id = {u["_id"]: u for u in users.values()}

    await _chunked([save_profile(db, users[s.index]["_id"], ProfileIn(**s.profile)) for s in plans_students])
    plans = plan_projects(plans_students, projects, seed)
    created = []
    # event teams first and sequentially, so the one-team-per-event rule is exercised deterministically
    for plan in [p for p in plans if p.payload.get("event_key")]:
        created.append(await _execute_project(db, plan, users, stats))
    others = [p for p in plans if not p.payload.get("event_key")]
    created += await _chunked([_execute_project(db, p, users, stats) for p in others], size=6)
    for p in created:
        if p:
            await _team_chat(db, p, users_by_id, rng)
    stats["direct_conversations"] = await _direct_chats(db, plans_students, users, direct_chats, rng)
    await _backdate(db, users_by_id, rng)

    if research:
        scenarios = generate_scenarios(seed=42)
        stats["research_scenarios"] = len(await research_svc.import_scenarios(db, scenarios, {"_id": None}))
        if encoder is not None:
            for s in scenarios[:packets]:
                await research_svc.build_packet(db, encoder, s["scenario_id"])
            stats["rating_packets"] = packets

    stats["case_coverage"] = {name: sum(1 for s in plans_students if name in s.cases)
                              for name in sorted({c for s in plans_students for c in s.cases})}
    stats["project_cases"] = [p.case["name"] for p in plans]
    return stats


async def summary(db) -> dict[str, Any]:
    demo = {"email": {"$regex": f"@{re.escape(DEMO_DOMAIN)}$"}}
    ids = [u["_id"] async for u in db.users.find(demo, {"_id": 1})]
    inv_status: dict[str, int] = {}
    async for i in db.invitations.find({"candidate_id": {"$in": ids}}, {"status": 1, "kind": 1}):
        key = f"{i['kind']}:{i['status']}"
        inv_status[key] = inv_status.get(key, 0) + 1
    return {
        "users": len(ids),
        "visible_profiles": await db.profiles.count_documents({"_id": {"$in": ids}, "visible": True}),
        "hidden_profiles": await db.profiles.count_documents({"_id": {"$in": ids}, "visible": False}),
        "profiles_without_availability": await db.profiles.count_documents({"_id": {"$in": ids}, "availability": None}),
        "projects": await db.projects.count_documents({"demo": True}),
        "projects_full": await db.projects.count_documents({"demo": True, "open_positions": 0}),
        "projects_closed": await db.projects.count_documents({"demo": True, "status": "closed"}),
        "projects_private": await db.projects.count_documents({"demo": True, "visibility": "private"}),
        "invitations_by_kind_status": dict(sorted(inv_status.items())),
        "conversations": await db.conversations.count_documents({"participant_ids": {"$in": ids}}),
        "messages": await db.messages.count_documents({"sender_id": {"$in": ids}}),
        "embeddings_cached": await db.embeddings.count_documents({"user_id": {"$in": ids}}),
        "research_scenarios_synthetic": await db.research_scenarios.count_documents({"provenance": "synthetic"}),
    }
