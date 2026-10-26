"""The five compared methods (paper Section 5.1).

M1 Skill overlap        sum_{s in S, c lists s} a_s / sum_{s in S} a_s   (team ignored)
M2 TF-IDF               cos(tfidf(profile text), tfidf(project text))   (team ignored)
M3 Semantic only        f_sem                                           (team ignored)
M4 Semantic + skill gap f_sem, f_gap with weights 0.30/0.35 rescaled to sum to one
M5 Full Assembl         all five features, initial or calibrated weights

Every method ranks exactly the same eligible pool (mandatory rules applied
once, before any method runs). M1-M3 sort by (score desc, candidate id asc):
they must not use team-dependent tie-breakers, otherwise the
changed-membership check (Section 5.2) would be contaminated.

M4/M5 are scored through :class:`FeatureTable`, which precomputes the
weight-independent feature values once per scenario so calibration can try
many weight vectors cheaply. ``tests/research`` checks that it reproduces
:func:`app.domain.engine.rank_candidates` exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.domain.eligibility import EligibilityDecision, check_eligibility
from app.domain.engine import rank_candidates
from app.domain.features import team_slots
from app.domain.models import ProjectSpec, RecommendationRequest, StudentProfile
from app.domain.scoring import FEATURES, INITIAL_WEIGHTS, ranking_key, renormalize
from app.domain.semantic import profile_text, project_text

from .scenario import Scenario

METHODS = ("M1", "M2", "M3", "M4", "M5")
METHOD_NAMES = {
    "M1": "Skill overlap",
    "M2": "TF-IDF",
    "M3": "Semantic only",
    "M4": "Semantic + skill gap",
    "M5": "Full Assembl",
}
M4_WEIGHTS = {"sem": INITIAL_WEIGHTS["sem"], "gap": INITIAL_WEIGHTS["gap"]}


def eligible_pool(scenario: Scenario, team: tuple[StudentProfile, ...] | None = None) -> tuple[list[StudentProfile], list[EligibilityDecision]]:
    team = scenario.team if team is None else team
    slots = team_slots(scenario.project, team)
    decisions = [
        check_eligibility(scenario.project, team, c, slots, scenario.committed_elsewhere) for c in scenario.candidates
    ]
    eligible = {d.candidate_id for d in decisions if d.eligible}
    return [c for c in scenario.candidates if c.user_id in eligible], decisions


def _sorted_ids(scores: Mapping[str, float]) -> list[str]:
    return [cid for cid, _ in sorted(scores.items(), key=lambda kv: (-round(kv[1], 12), kv[0]))]


def m1_scores(project: ProjectSpec, pool: list[StudentProfile]) -> dict[str, float]:
    total = sum(r.importance for r in project.requirements)
    return {
        c.user_id: sum(r.importance for r in project.requirements if c.skill_status(r.skill) == "stated") / total
        for c in pool
    }


def m2_scores(project: ProjectSpec, pool: list[StudentProfile]) -> dict[str, float]:
    """TF-IDF fitted per scenario on the project text plus the pool's profile texts."""
    if not pool:
        return {}
    ptext = project_text(project)
    texts = [profile_text(c) for c in pool]
    vec = TfidfVectorizer(lowercase=True, token_pattern=r"(?u)\b[\w+#.]+\b")
    try:
        mat = vec.fit_transform([ptext, *texts])
    except ValueError:  # empty vocabulary
        return {c.user_id: 0.0 for c in pool}
    sims = cosine_similarity(mat[1:], mat[0:1]).ravel()
    return {c.user_id: float(max(0.0, s)) for c, s in zip(pool, sims)}


@dataclass
class FeatureTable:
    """Weight-independent feature values for one scenario's eligible pool."""

    ids: list[str]
    values: dict[str, dict[str, float | None]]
    gains: dict[str, float]
    available: frozenset[str]

    @classmethod
    def build(cls, scenario: Scenario, pool: list[StudentProfile], semantic: Mapping[str, float],
              team: tuple[StudentProfile, ...] | None = None) -> "FeatureTable":
        team = scenario.team if team is None else team
        request = RecommendationRequest(scenario.project, team, tuple(pool), dict(semantic), scenario.committed_elsewhere)
        result = rank_candidates(request, INITIAL_WEIGHTS)
        if result.status == "team_full":
            return cls([], {}, {}, frozenset())
        return cls(
            ids=[r.candidate_id for r in result.ranked],
            values={r.candidate_id: r.feature_values() for r in result.ranked},
            gains={r.candidate_id: r.gain for r in result.ranked},
            available=frozenset(k for k in FEATURES if k not in result.omitted_features),
        )

    def rank(self, weights: Mapping[str, float]) -> tuple[list[str], dict[str, float]]:
        if not self.ids:
            return [], {}
        active = renormalize(weights, self.available)
        scores = {cid: sum(w * (self.values[cid][k] or 0.0) for k, w in active.items()) for cid in self.ids}
        order = sorted(
            self.ids,
            key=lambda cid: ranking_key(scores[cid], self.values[cid]["gap"], self.values[cid]["sem"] or 0.0, cid),
        )
        return order, scores


def run_methods(
    scenario: Scenario,
    pool: list[StudentProfile],
    semantic: Mapping[str, float],
    m5_weights: Mapping[str, float] = INITIAL_WEIGHTS,
    table: FeatureTable | None = None,
) -> dict[str, list[str]]:
    table = table or FeatureTable.build(scenario, pool, semantic)
    sem_pool = {c.user_id: semantic[c.user_id] for c in pool}
    return {
        "M1": _sorted_ids(m1_scores(scenario.project, pool)),
        "M2": _sorted_ids(m2_scores(scenario.project, pool)),
        "M3": _sorted_ids(sem_pool),
        "M4": table.rank(M4_WEIGHTS)[0],
        "M5": table.rank(m5_weights)[0],
    }
