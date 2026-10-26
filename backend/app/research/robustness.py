"""Robustness checks (paper Section 5.2)."""

from __future__ import annotations

import copy
import random
from dataclasses import replace
from typing import Callable, Mapping

from app.domain.engine import rank_candidates
from app.domain.features import team_slots
from app.domain.models import RecommendationRequest, StudentProfile
from app.domain.skills import SkillRegistry

from .methods import METHODS, FeatureTable, eligible_pool, run_methods
from .metrics import ndcg_at_k
from .scenario import Scenario, scenario_from_dict
from .stats import kendall_tau

SemanticFn = Callable[[Scenario, list[StudentProfile]], dict[str, float]]

# Pairs that must never be merged by the alias table.
DISTINCT_PAIRS = [("React", "React Native"), ("Python", "Django"), ("Java", "JavaScript"), ("C", "C++"), ("C++", "C#")]


def hide_profile_information(scenario: Scenario, share: float, seed: int) -> Scenario:
    """Randomly move a share of listed skills to *not stated* and blank out
    availability for the same share of candidates. Labels are kept: the
    question is how much ranking quality degrades on the same judgments."""
    rng = random.Random(f"{seed}:{scenario.scenario_id}:{share}")
    cands = []
    for c in scenario.candidates:
        skills = {s: v for s, v in c.skills.items() if rng.random() >= share}
        avail = None if rng.random() < share else c.availability
        cands.append(replace(c, skills=skills, availability=avail))
    return replace(scenario, candidates=tuple(cands))


def incomplete_profiles(scenarios: list[Scenario], semantic_fn: SemanticFn, m5_weights: Mapping[str, float],
                        shares=(0.2, 0.4), seed: int = 0, k: int = 5) -> dict:
    out: dict = {}
    for share in shares:
        deltas: dict[str, list[float]] = {m: [] for m in METHODS}
        for s in scenarios:
            labels = s.labels({c.user_id for c in eligible_pool(s)[0]})
            if not labels:
                continue
            ndcg: list[dict[str, float | None]] = []
            for variant in (s, hide_profile_information(s, share, seed)):
                pool, _ = eligible_pool(variant)
                ranks = run_methods(variant, pool, semantic_fn(variant, pool), m5_weights)
                ndcg.append({m: ndcg_at_k(ranks[m], labels, k) for m in METHODS})
            for m in METHODS:
                before, after = ndcg[0][m], ndcg[1][m]
                if before is not None and after is not None:
                    deltas[m].append(after - before)
        out[str(share)] = {
            m: {"mean_delta_ndcg@5": (sum(d) / len(d)) if d else None, "n": len(d)} for m, d in deltas.items()
        }
    return out


def label_variants(scenarios: list[Scenario], registry: SkillRegistry, semantic_fn: SemanticFn,
                   m5_weights: Mapping[str, float], seed: int = 0) -> dict:
    """Rewrite skills with known aliases/case variants and check that rankings
    are unchanged; also check that distinct technologies stay distinct."""
    rng = random.Random(seed)
    aliases: dict[str, list[str]] = {}
    for canon in registry.canonical_labels:
        aliases[canon] = [canon.lower(), canon.upper(), f"  {canon}  "]
    raw_table = registry._alias  # explicit aliases, keyed lower-case
    for alias_key, canon in raw_table.items():
        aliases.setdefault(canon, []).append(alias_key)

    def rewrite(skills: dict) -> dict:
        return {rng.choice(aliases.get(s, [s])): v for s, v in skills.items()}

    identical = 0
    checked = 0
    for s in scenarios:
        raw = copy.deepcopy(s.raw)
        if not raw:
            continue
        for group in ("team", "candidates"):
            for p in raw[group]:
                p["skills"] = rewrite(p.get("skills") or {})
        for r in raw["project"]["requirements"]:
            r["skill"] = rng.choice(aliases.get(r["skill"], [r["skill"]]))
        variant = scenario_from_dict(raw, registry)
        a_pool, _ = eligible_pool(s)
        b_pool, _ = eligible_pool(variant)
        a = run_methods(s, a_pool, semantic_fn(s, a_pool), m5_weights)
        b = run_methods(variant, b_pool, semantic_fn(variant, b_pool), m5_weights)
        checked += 1
        identical += int(a == b)
    distinct = {f"{x} / {y}": registry.normalize(x).canonical != registry.normalize(y).canonical for x, y in DISTINCT_PAIRS}
    return {"scenarios_checked": checked, "rankings_identical": identical, "distinct_technologies_kept_separate": distinct}


def limited_availability(scenarios: list[Scenario], threshold: float = 0.3) -> list[str]:
    """Synchronous scenarios in which fewer than ``threshold`` of eligible
    candidates reach the requested number of shared slots."""
    out = []
    for s in scenarios:
        if not s.project.synchronous:
            continue
        pool, _ = eligible_pool(s)
        slots = team_slots(s.project, s.team)
        if not pool or slots.slots is None:
            continue
        ok = sum(1 for c in pool if c.availability is not None and len(c.availability & slots.slots) >= s.project.min_shared_slots)
        if ok / len(pool) < threshold:
            out.append(s.scenario_id)
    return out


def covering_member(s: Scenario, uid: str = "robustness-covering-member") -> StudentProfile:
    slots = team_slots(s.project, s.team).slots
    return StudentProfile(
        user_id=uid,
        skills={r.skill: r.desired_proficiency for r in s.project.requirements},
        availability=slots if slots is not None else None,
    )


def already_covered(scenarios: list[Scenario], semantic_fn: SemanticFn, m5_weights: Mapping[str, float]) -> dict:
    passed, failures = 0, []
    for s in scenarios:
        team = (*s.team, covering_member(s))
        project = replace(s.project, target_size=max(s.project.target_size, len(team) + 1))
        variant = replace(s, team=team, project=project)
        pool, _ = eligible_pool(variant)
        try:
            res = rank_candidates(RecommendationRequest(project, team, tuple(pool), semantic_fn(variant, pool),
                                                        s.committed_elsewhere), m5_weights)
            ok = (res.team_coverage.complete and "gap" in res.omitted_features and "gap" not in res.active_weights
                  and abs(sum(res.active_weights.values()) - 1) < 1e-9 and len(res.ranked) == len(pool))
        except Exception as exc:  # noqa: BLE001 - recorded as a failed check
            ok, res = False, exc
        if ok:
            passed += 1
        else:
            failures.append(s.scenario_id)
    return {"scenarios": len(scenarios), "passed": passed, "failed": failures}


def changed_membership(scenarios: list[Scenario], semantic_fn: SemanticFn, m5_weights: Mapping[str, float]) -> dict:
    """Same project, requirements and candidates; different existing team.
    Team-independent methods (M1-M3) must produce identical rankings (tau = 1)
    over candidates eligible under both teams; M4/M5 may change."""
    per_method: dict[str, list[float]] = {m: [] for m in METHODS}
    integrity_failures: list[str] = []
    for s in scenarios:
        base_cov = {r.skill: 0 for r in s.project.requirements}
        for m in s.team:
            for r in s.project.requirements:
                base_cov[r.skill] = max(base_cov[r.skill], m.skills.get(r.skill, 0))
        # replace the last member by someone covering the requirement the team lacks most
        weakest = min(s.project.requirements, key=lambda r: (base_cov[r.skill] / r.desired_proficiency, -r.importance))
        newcomer = StudentProfile(user_id="robustness-new-member", skills={weakest.skill: 4},
                                  availability=s.team[-1].availability)
        alt_team = (*s.team[:-1], newcomer)
        alt = replace(s, team=alt_team)
        pool_a, _ = eligible_pool(s)
        pool_b, _ = eligible_pool(alt)
        common_ids = {c.user_id for c in pool_a} & {c.user_id for c in pool_b}
        pool = [c for c in pool_a if c.user_id in common_ids]
        sem = semantic_fn(s, pool)
        ra = run_methods(s, pool, sem, m5_weights, FeatureTable.build(s, pool, sem))
        rb = run_methods(alt, pool, sem, m5_weights, FeatureTable.build(alt, pool, sem, alt_team))
        for m in METHODS:
            tau = kendall_tau(ra[m], rb[m])
            if tau is not None:
                per_method[m].append(tau)
        if any(ra[m] != rb[m] for m in ("M1", "M2", "M3")):
            integrity_failures.append(s.scenario_id)
    return {
        "per_method_mean_kendall_tau": {m: (sum(v) / len(v) if v else None) for m, v in per_method.items()},
        "n": {m: len(v) for m, v in per_method.items()},
        "team_independent_methods_unchanged": not integrity_failures,
        "integrity_failures": integrity_failures,
    }
