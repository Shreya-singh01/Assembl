"""Candidate pooling for human judgments (paper Section 4.6, "Candidate sets").

Top-n candidates from every method are pooled, a few random eligible
candidates are added so judgments are not limited to what one method prefers,
and the pool is shuffled. Raters see anonymised labels (C01, C02, ...), never
method names or scores. Everything is seeded and therefore reproducible.
"""

from __future__ import annotations

import random
from typing import Any, Mapping, Sequence

from app.domain.models import StudentProfile


def build_pool(
    rankings: Mapping[str, Sequence[str]], eligible_ids: Sequence[str], top_n: int = 10, extra: int = 3, seed: int = 0
) -> list[str]:
    pooled: set[str] = set()
    for method in sorted(rankings):
        pooled.update(rankings[method][:top_n])
    rng = random.Random(seed)
    rest = sorted(set(eligible_ids) - pooled)
    pooled.update(rng.sample(rest, min(extra, len(rest))))
    order = sorted(pooled)
    rng.shuffle(order)
    return order


def anonymized_profile(p: StudentProfile, label: str) -> dict[str, Any]:
    """What a rater sees: no id, name, e-mail or any contact field."""
    return {
        "label": label,
        "year": p.year,
        "branch": p.branch,
        "skills": [{"skill": s, "proficiency": v} for s, v in sorted(p.skills.items())],
        "primary_roles": list(p.primary_roles),
        "secondary_roles": list(p.secondary_roles),
        "interests": list(p.interests),
        "project_summaries": list(p.project_summaries),
        "availability": None if p.availability is None else sorted(p.availability),
        "weekly_hours": p.weekly_hours,
        "work_mode": p.work_mode,
    }


def judging_packet(scenario, pool_ids: Sequence[str]) -> dict[str, Any]:
    by_id = {c.user_id: c for c in scenario.candidates}
    labels = {cid: f"C{i + 1:02d}" for i, cid in enumerate(pool_ids)}
    return {
        "scenario_id": scenario.scenario_id,
        "project": {
            "title": scenario.project.title,
            "description": scenario.project.description,
            "requirements": [
                {"skill": r.skill, "importance": r.importance_label, "desired_proficiency": r.desired_proficiency}
                for r in scenario.project.requirements
            ],
            "vacant_roles": list(scenario.project.vacant_roles),
            "weekly_hours": scenario.project.weekly_hours,
            "work_mode": scenario.project.work_mode,
            "synchronous": scenario.project.synchronous,
        },
        "team": [anonymized_profile(m, f"Member {i + 1}") for i, m in enumerate(scenario.team)],
        "candidates": [anonymized_profile(by_id[cid], labels[cid]) for cid in pool_ids],
        "rating_scale": {"0": "not suitable", "1": "marginally suitable", "2": "suitable", "3": "strongly suitable"},
        # Kept by the coordinator only; never shown to raters.
        "_label_to_candidate": {v: k for k, v in labels.items()},
    }
