"""Ranking metrics (paper Section 4.6).

Documented implementation decisions
-----------------------------------
* **NDCG@k gain** - the mean rating itself (linear gain, 0-3) with discount
  1/log2(rank + 1); IDCG uses the ideal ordering of *all* judged candidates for
  the scenario. If IDCG is 0 (every judged candidate rated 0) NDCG is
  undefined (``None``) and the scenario is left out of the macro-average,
  with the count reported.
* **Unjudged candidates** - never treated as rating 0. Label-based metrics use
  the *condensed list*: unjudged candidates are removed from the ranking
  before the cutoff. Pooling makes this rare (each method's top 10 is judged)
  and ``judged_at_k`` is reported so it stays visible.
* **Precision@k** - relevant iff mean rating >= 2; the denominator is
  ``min(k, number of judged candidates in the condensed ranking)``, so a
  scenario with fewer than k eligible candidates is not penalised for
  missing slots.
* **Added skill coverage@k** - mean G(c, T) over the method's raw top k
  (computed from profiles; no labels needed).
* **Constraint violations@k** - share of the raw top k with at least one
  *soft* conflict (see :func:`soft_violations`). Mandatory-rule violations are
  counted separately and should always be 0 because every method ranks the
  filtered pool.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from app.domain.coverage import marginal_gain
from app.domain.eligibility import check_eligibility
from app.domain.features import TeamSlots, availability_overlap, mode_compatibility
from app.domain.models import ProjectSpec, StudentProfile

RELEVANCE_THRESHOLD = 2.0


def _condensed(ranked: Sequence[str], labels: Mapping[str, float]) -> list[str]:
    return [cid for cid in ranked if cid in labels]


def dcg(gains: Sequence[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked: Sequence[str], labels: Mapping[str, float], k: int = 5) -> float | None:
    if not labels:
        return None
    ideal = dcg(sorted(labels.values(), reverse=True)[:k])
    if ideal <= 0:
        return None
    got = dcg([labels[c] for c in _condensed(ranked, labels)[:k]])
    return got / ideal


def precision_at_k(ranked: Sequence[str], labels: Mapping[str, float], k: int = 5) -> float | None:
    top = _condensed(ranked, labels)[:k]
    if not top:
        return None
    return sum(1 for c in top if labels[c] >= RELEVANCE_THRESHOLD) / len(top)


def judged_at_k(ranked: Sequence[str], labels: Mapping[str, float], k: int = 5) -> float | None:
    top = list(ranked)[:k]
    return None if not top else sum(1 for c in top if c in labels) / len(top)


def added_coverage_at_k(
    ranked: Sequence[str], project: ProjectSpec, team: Sequence[StudentProfile],
    by_id: Mapping[str, StudentProfile], k: int = 5,
) -> float | None:
    top = list(ranked)[:k]
    if not top:
        return None
    return sum(marginal_gain(project.requirements, team, by_id[c])[0] for c in top) / len(top)


def soft_violations(project: ProjectSpec, slots: TeamSlots, cand: StudentProfile) -> list[str]:
    """Conflicts with stated *preferred* (non-mandatory) conditions."""
    out: list[str] = []
    if project.synchronous and not project.availability_mandatory:
        overlap = availability_overlap(cand, slots)
        if overlap == 0:
            out.append("zero_shared_availability")
    if project.work_mode and cand.work_mode and mode_compatibility(project.work_mode, cand.work_mode) == 0:
        out.append("incompatible_work_mode")
    if project.vacant_roles and not project.role_mandatory and (cand.primary_roles or cand.secondary_roles):
        if not (project.vacant_role_keys & (cand.primary_role_keys | cand.secondary_role_keys)):
            out.append("prefers_no_vacant_role")
    return out


def violations_at_k(
    ranked: Sequence[str], project: ProjectSpec, team: Sequence[StudentProfile], slots: TeamSlots,
    by_id: Mapping[str, StudentProfile], committed: frozenset[str] = frozenset(), k: int = 5,
) -> dict:
    top = list(ranked)[:k]
    per = {c: soft_violations(project, slots, by_id[c]) for c in top}
    mandatory = sum(
        1 for c in top if not check_eligibility(project, team, by_id[c], slots, committed).eligible
    )
    kinds: dict[str, int] = {}
    for v in per.values():
        for kind in v:
            kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "soft_violation_rate": (sum(1 for v in per.values() if v) / len(top)) if top else None,
        "soft_violation_kinds": kinds,
        "mandatory_violations": mandatory,
    }
