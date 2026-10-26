"""Team skill coverage and candidate contribution (paper Eqs. 2-5).

    C_s(T)        = min(1, max_{u in T} p_{u,s} / r_s)                      (2)
    Coverage(T)   = sum_s a_s C_s(T) / sum_s a_s                            (3)
    G(c, T)       = Coverage(T u {c}) - Coverage(T)                         (4)
    f_gap(c, T)   = G(c, T) / (1 - Coverage(T)),   defined iff Coverage(T)<1 (5)

Known limitation (paper Section 4.3): a requirement is covered by the team's
strongest member alone, so workload and the need for several specialists in
the same skill are not modelled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .models import DomainValidationError, Requirement, StudentProfile

EPS = 1e-9


@dataclass(frozen=True)
class SkillCoverage:
    skill: str
    importance: int
    desired_proficiency: int
    best_proficiency: float
    coverage: float


@dataclass(frozen=True)
class CoverageReport:
    overall: float
    per_skill: tuple[SkillCoverage, ...]

    @property
    def complete(self) -> bool:
        return self.overall >= 1.0 - EPS

    def by_skill(self) -> dict[str, SkillCoverage]:
        return {s.skill: s for s in self.per_skill}


def _validate(requirements: Sequence[Requirement]) -> None:
    if not requirements:
        raise DomainValidationError("coverage needs a non-empty set of required skills")
    if sum(r.importance for r in requirements) <= 0:
        raise DomainValidationError("sum of requirement importances must be positive")
    for r in requirements:
        if r.desired_proficiency <= 0:
            raise DomainValidationError(f"desired proficiency for {r.skill!r} must be positive")


def skill_coverage(
    requirement: Requirement, members: Iterable[StudentProfile], unknown_value: float = 0.0
) -> SkillCoverage:
    best = max((m.proficiency(requirement.skill, unknown_value) for m in members), default=0.0)
    return SkillCoverage(
        skill=requirement.skill,
        importance=requirement.importance,
        desired_proficiency=requirement.desired_proficiency,
        best_proficiency=best,
        coverage=min(1.0, best / requirement.desired_proficiency),
    )


def team_coverage(
    requirements: Sequence[Requirement], members: Sequence[StudentProfile], unknown_value: float = 0.0
) -> CoverageReport:
    _validate(requirements)
    per = tuple(skill_coverage(r, members, unknown_value) for r in requirements)
    total = sum(r.importance for r in requirements)
    overall = sum(s.importance * s.coverage for s in per) / total
    return CoverageReport(overall=min(1.0, max(0.0, overall)), per_skill=per)


def marginal_gain(
    requirements: Sequence[Requirement],
    team: Sequence[StudentProfile],
    candidate: StudentProfile,
    unknown_value: float = 0.0,
    *,
    base: CoverageReport | None = None,
) -> tuple[float, CoverageReport]:
    """Return G(c, T) and the coverage report of T u {c}.

    Adding a member can never lower a max-based coverage, so tiny negative
    floating-point residues are clamped to zero."""
    base = base or team_coverage(requirements, team, unknown_value)
    after = team_coverage(requirements, [*team, candidate], unknown_value)
    gain = after.overall - base.overall
    if gain < 0:
        if gain < -1e-7:  # pragma: no cover - would indicate a bug in Eq. (2)
            raise AssertionError(f"coverage decreased after adding a member ({gain})")
        gain = 0.0
    return gain, after


def gap_feature(gain: float, base_coverage: float) -> float | None:
    """f_gap (Eq. 5). ``None`` means undefined: the team already covers every
    stated requirement and the feature must be dropped for this request."""
    remaining = 1.0 - base_coverage
    if remaining <= EPS:
        return None
    return min(1.0, max(0.0, gain / remaining))
