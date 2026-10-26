"""Weighted ranking score (paper Eq. 6) with proportional weight renormalisation.

    Score(c | P, T) = sum_{k in K} w_k f_k(c, P, T),  w_k >= 0,  sum w_k = 1

The initial weights below are the paper's design choices, *not* calibrated or
optimal values. The score is a relative ranking value for one request, not a
probability that a team will succeed.
"""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping

from .models import DomainValidationError

FEATURES: tuple[str, ...] = ("sem", "gap", "role", "avail", "work")
FEATURE_LABELS = {
    "sem": "Semantic relevance",
    "gap": "Skill-gap contribution",
    "role": "Vacant-role fit",
    "avail": "Shared availability",
    "work": "Commitment & working mode",
}
INITIAL_WEIGHTS: Mapping[str, float] = MappingProxyType(
    {"sem": 0.30, "gap": 0.35, "role": 0.15, "avail": 0.10, "work": 0.10}
)
SCORE_DECIMALS = 12  # rounding used for tie detection only


class NoActiveFeatures(DomainValidationError):
    pass


def validate_weights(weights: Mapping[str, float], *, require_unit_sum: bool = True) -> None:
    if not weights:
        raise DomainValidationError("at least one feature weight is required")
    unknown = set(weights) - set(FEATURES)
    if unknown:
        raise DomainValidationError(f"unknown features in weights: {sorted(unknown)}")
    for k, w in weights.items():
        if not isinstance(w, (int, float)) or not math.isfinite(w) or w < 0:
            raise DomainValidationError(f"weight for {k!r} must be a finite non-negative number")
    total = sum(weights.values())
    if total <= 0:
        raise DomainValidationError("weights must not all be zero")
    if require_unit_sum and abs(total - 1.0) > 1e-6:
        raise DomainValidationError(f"weights must sum to 1, got {total}")


def renormalize(weights: Mapping[str, float], available: set[str] | frozenset[str]) -> dict[str, float]:
    """w'_k = w_k / sum_{j in K_active} w_j over features that are configured
    (w > 0) and defined for this request."""
    active = {k: w for k, w in weights.items() if k in available and w > 0}
    total = sum(active.values())
    if total <= 0:
        raise NoActiveFeatures("no configured feature is defined for this request")
    return {k: w / total for k, w in active.items()}


def weighted_score(values: Mapping[str, float], active_weights: Mapping[str, float]) -> float:
    missing = set(active_weights) - set(values)
    if missing:
        raise DomainValidationError(f"missing feature values: {sorted(missing)}")
    return sum(active_weights[k] * values[k] for k in active_weights)


def ranking_key(score: float, gap: float | None, sem: float, candidate_id: str) -> tuple:
    """Score desc, then f_gap desc (when defined), then f_sem desc, then id asc."""
    return (
        -round(score, SCORE_DECIMALS),
        -round(gap, SCORE_DECIMALS) if gap is not None else 0.0,
        -round(sem, SCORE_DECIMALS),
        candidate_id,
    )
