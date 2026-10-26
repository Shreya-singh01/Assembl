"""Assembl ranking pipeline for one recruitment request (paper Figure 1, stages 2-4).

    eligibility filter -> feature computation -> weighted score -> explanation

The engine ranks candidates against the team *as it currently stands*. Filling
several positions is sequential: after someone joins, the caller rebuilds the
request with the new team and ranks again (paper Section 4.4). Selecting
several members jointly is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from .coverage import CoverageReport, gap_feature, marginal_gain, team_coverage
from .eligibility import EligibilityDecision, check_eligibility
from .explanations import build_explanation, render_text
from .features import FeatureValue, TeamSlots, availability_fit, role_fit, team_slots, work_fit
from .models import RecommendationRequest
from .scoring import FEATURES, INITIAL_WEIGHTS, ranking_key, renormalize, validate_weights, weighted_score

Status = Literal["ok", "team_full", "no_eligible_candidates"]


@dataclass(frozen=True)
class RankedCandidate:
    candidate_id: str
    rank: int
    score: float
    features: dict[str, FeatureValue]
    gain: float
    coverage_after: float
    explanation: dict[str, Any]
    explanation_text: str

    def feature_values(self) -> dict[str, float | None]:
        return {k: v.value for k, v in self.features.items()}


@dataclass(frozen=True)
class RankingResult:
    status: Status
    team_coverage: CoverageReport
    team_slots: TeamSlots
    configured_weights: dict[str, float]
    active_weights: dict[str, float]
    omitted_features: dict[str, str]
    weights_renormalized: bool
    ranked: list[RankedCandidate]
    eligibility: list[EligibilityDecision]
    open_positions: int
    warnings: list[str] = field(default_factory=list)

    @property
    def excluded(self) -> list[EligibilityDecision]:
        return [d for d in self.eligibility if not d.eligible]


def _request_level_omissions(
    request: RecommendationRequest, weights: Mapping[str, float], base: CoverageReport, slots: TeamSlots
) -> dict[str, str]:
    """Features undefined for every candidate in this request, with reasons."""
    project = request.project
    omitted: dict[str, str] = {}
    if base.complete:
        omitted["gap"] = "all_requirements_covered"
    if not project.vacant_roles:
        omitted["role"] = "no_vacant_roles"
    if not project.synchronous:
        omitted["avail"] = "team_not_synchronous"
    elif slots.slots is None:
        omitted["avail"] = "team_availability_not_stated"
    if project.weekly_hours is None and project.work_mode is None:
        omitted["work"] = "team_states_no_commitment_or_mode"
    return {k: v for k, v in omitted.items() if weights.get(k, 0) > 0}


def rank_candidates(
    request: RecommendationRequest,
    weights: Mapping[str, float] = INITIAL_WEIGHTS,
    *,
    unknown_proficiency: float = 0.0,
    require_unit_sum: bool = True,
) -> RankingResult:
    validate_weights(weights, require_unit_sum=require_unit_sum)
    project, team = request.project, request.team
    base = team_coverage(project.requirements, team, unknown_proficiency)
    slots = team_slots(project, team)
    open_positions = max(0, project.target_size - len(team))

    warnings: list[str] = []
    if project.synchronous and slots.slots is None:
        warnings.append("No current member has stated weekly availability; shared availability cannot be scored or enforced.")
    elif project.synchronous and slots.slots is not None and not slots.slots:
        warnings.append("Current members share no common weekly slot under the selected policy.")

    omitted = _request_level_omissions(request, weights, base, slots)
    available = {k for k in FEATURES if k not in omitted}
    active = renormalize(weights, available)
    renormalized = bool(omitted)

    if open_positions == 0:
        return RankingResult(
            "team_full", base, slots, dict(weights), active, omitted, renormalized, [], [], 0,
            ["The team has reached its target size; no further recommendations are produced."],
        )

    decisions: list[EligibilityDecision] = []
    scored: list[tuple[tuple, RankedCandidate]] = []
    for cand in request.candidates:
        decision = check_eligibility(project, team, cand, slots, request.committed_elsewhere)
        decisions.append(decision)
        if not decision.eligible:
            continue

        sem = request.semantic.get(cand.user_id)
        if sem is None:
            raise ValueError(f"missing semantic score for candidate {cand.user_id}")
        sem = min(1.0, max(0.0, float(sem)))
        gain, after = marginal_gain(project.requirements, team, cand, unknown_proficiency, base=base)
        gap = gap_feature(gain, base.overall)
        feats: dict[str, FeatureValue] = {
            "sem": FeatureValue(sem, "computed"),
            "gap": FeatureValue(gap, "computed") if gap is not None else FeatureValue.omitted("all_requirements_covered"),
            "role": role_fit(project, cand),
            "avail": availability_fit(project, slots, cand),
            "work": work_fit(project, cand),
        }
        values = {k: feats[k].value for k in active}
        if any(v is None for v in values.values()):  # pragma: no cover - guarded by request-level omission
            raise AssertionError("an active feature is undefined for a candidate")
        score = weighted_score(values, active)  # type: ignore[arg-type]
        expl = build_explanation(
            project, cand, base, after, gain, feats, active, omitted, renormalized, decision.unverified
        )
        rc = RankedCandidate(cand.user_id, 0, score, feats, gain, after.overall, expl, render_text(expl))
        scored.append((ranking_key(score, gap, sem, cand.user_id), rc))

    scored.sort(key=lambda t: t[0])
    ranked = [
        RankedCandidate(rc.candidate_id, i + 1, rc.score, rc.features, rc.gain, rc.coverage_after, rc.explanation, rc.explanation_text)
        for i, (_, rc) in enumerate(scored)
    ]
    status: Status = "ok" if ranked else "no_eligible_candidates"
    return RankingResult(
        status, base, slots, dict(weights), active, omitted, renormalized, ranked, decisions, open_positions, warnings
    )
