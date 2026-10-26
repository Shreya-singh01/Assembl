"""Domain value objects: student profiles, requirements and recruitment requests.

Unknown versus absent (paper Section 4.1): a skill the student did not list is
*not stated*; only an explicit "none" is *declared absent*. Both contribute zero
to Eq. (2) in the paper's formulation, but they are kept distinct so that
explanations never present an unstated skill as a confirmed lack of it.
Availability uses ``None`` for "not stated" and an empty set for "stated: none".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

PROFICIENCY_MIN = 1
PROFICIENCY_MAX = 4
PROFICIENCY_LABELS = {
    1: "learning / tutorial level",
    2: "used in one project",
    3: "used in several projects / could lead that part",
    4: "advanced, able to guide others",
}

IMPORTANCE_LABELS = {1: "useful", 2: "important", 3: "essential"}

WORK_MODES = ("online", "offline", "hybrid")
# Weekly-hours range offered on the forms. H_max in f_work is the largest
# possible difference on the form (paper Section 4.4).
HOURS_MIN = 1
HOURS_MAX = 40

AvailabilityPolicy = Literal["all", "majority"]
UnverifiablePolicy = Literal["exclude", "include"]
SkillStatus = Literal["stated", "absent", "unknown"]


class DomainValidationError(ValueError):
    """Raised when inputs violate the model's preconditions."""


def role_key(role: str) -> str:
    return " ".join(role.split()).lower()


def _check_hours(value: int | None, what: str) -> None:
    if value is not None and not (HOURS_MIN <= value <= HOURS_MAX):
        raise DomainValidationError(f"{what} must be between {HOURS_MIN} and {HOURS_MAX}, got {value}")


def _check_mode(value: str | None, what: str) -> None:
    if value is not None and value not in WORK_MODES:
        raise DomainValidationError(f"{what} must be one of {WORK_MODES}, got {value!r}")


@dataclass(frozen=True, eq=False)
class StudentProfile:
    user_id: str
    skills: Mapping[str, int] = field(default_factory=dict)
    """Canonical skill label -> self-reported proficiency (1-4)."""
    declared_absent: frozenset[str] = frozenset()
    year: int | None = None
    branch: str | None = None
    primary_roles: tuple[str, ...] = ()
    secondary_roles: tuple[str, ...] = ()
    interests: tuple[str, ...] = ()
    project_summaries: tuple[str, ...] = ()
    availability: frozenset[str] | None = None
    weekly_hours: int | None = None
    work_mode: str | None = None
    visible: bool = True

    def __post_init__(self) -> None:
        if not self.user_id:
            raise DomainValidationError("user_id is required")
        for skill, level in self.skills.items():
            if not isinstance(level, int) or isinstance(level, bool) or not (
                PROFICIENCY_MIN <= level <= PROFICIENCY_MAX
            ):
                raise DomainValidationError(
                    f"proficiency for {skill!r} must be an integer {PROFICIENCY_MIN}-{PROFICIENCY_MAX}, got {level!r}"
                )
        overlap = set(self.skills) & set(self.declared_absent)
        if overlap:
            raise DomainValidationError(f"skills both stated and declared absent: {sorted(overlap)}")
        _check_hours(self.weekly_hours, "weekly_hours")
        _check_mode(self.work_mode, "work_mode")

    def skill_status(self, skill: str) -> SkillStatus:
        if skill in self.skills:
            return "stated"
        if skill in self.declared_absent:
            return "absent"
        return "unknown"

    def proficiency(self, skill: str, unknown_value: float = 0.0) -> float:
        """p_{u,s}. Paper Eq. (2) uses 0 for both unknown and absent skills;
        ``unknown_value`` exists only for the clearly labelled experimental variant."""
        if skill in self.skills:
            return float(self.skills[skill])
        if skill in self.declared_absent:
            return 0.0
        return float(unknown_value)

    @property
    def primary_role_keys(self) -> frozenset[str]:
        return frozenset(role_key(r) for r in self.primary_roles)

    @property
    def secondary_role_keys(self) -> frozenset[str]:
        return frozenset(role_key(r) for r in self.secondary_roles)


@dataclass(frozen=True)
class Requirement:
    skill: str
    """Canonical skill label."""
    importance: int
    """a_s in {1, 2, 3}: useful, important, essential (ranking weight)."""
    desired_proficiency: int
    """r_s on the 1-4 scale."""
    mandatory: bool = False
    """Eligibility rule: every new member must state proficiency >= r_s.
    Deliberately separate from importance (see docs/research-methodology.md)."""

    def __post_init__(self) -> None:
        if not self.skill:
            raise DomainValidationError("requirement skill is required")
        if self.importance not in IMPORTANCE_LABELS:
            raise DomainValidationError(f"importance for {self.skill!r} must be 1, 2 or 3, got {self.importance!r}")
        if not isinstance(self.desired_proficiency, int) or not (
            PROFICIENCY_MIN <= self.desired_proficiency <= PROFICIENCY_MAX
        ):
            raise DomainValidationError(
                f"desired proficiency for {self.skill!r} must be {PROFICIENCY_MIN}-{PROFICIENCY_MAX}, got {self.desired_proficiency!r}"
            )

    @property
    def importance_label(self) -> str:
        return IMPORTANCE_LABELS[self.importance]


@dataclass(frozen=True)
class ProjectSpec:
    project_id: str
    description: str
    requirements: tuple[Requirement, ...]
    target_size: int
    title: str = ""
    vacant_roles: tuple[str, ...] = ()
    allowed_years: frozenset[int] | None = None
    role_mandatory: bool = False
    synchronous: bool = False
    min_shared_slots: int = 0
    availability_policy: AvailabilityPolicy = "all"
    availability_mandatory: bool = False
    weekly_hours: int | None = None
    work_mode: str | None = None
    unverifiable_policy: UnverifiablePolicy = "exclude"

    def __post_init__(self) -> None:
        if not self.requirements:
            raise DomainValidationError("a project needs at least one required skill")
        skills = [r.skill for r in self.requirements]
        if len(set(skills)) != len(skills):
            raise DomainValidationError("duplicate required skills")
        if self.target_size < 1:
            raise DomainValidationError("target_size must be at least 1")
        if self.synchronous and self.min_shared_slots < 1:
            raise DomainValidationError("synchronous projects must request at least one shared slot (h >= 1)")
        if self.min_shared_slots < 0:
            raise DomainValidationError("min_shared_slots cannot be negative")
        if self.availability_mandatory and not self.synchronous:
            raise DomainValidationError("mandatory shared availability requires a synchronous project")
        if self.role_mandatory and not self.vacant_roles:
            raise DomainValidationError("a mandatory role rule needs at least one vacant role")
        if self.availability_policy not in ("all", "majority"):
            raise DomainValidationError("availability_policy must be 'all' or 'majority'")
        if self.unverifiable_policy not in ("exclude", "include"):
            raise DomainValidationError("unverifiable_policy must be 'exclude' or 'include'")
        _check_hours(self.weekly_hours, "project weekly_hours")
        _check_mode(self.work_mode, "project work_mode")

    @property
    def vacant_role_keys(self) -> frozenset[str]:
        return frozenset(role_key(r) for r in self.vacant_roles)


@dataclass(frozen=True)
class RecommendationRequest:
    project: ProjectSpec
    team: tuple[StudentProfile, ...]
    candidates: tuple[StudentProfile, ...]
    semantic: Mapping[str, float]
    """f_sem per candidate id, already computed by the embedding service."""
    committed_elsewhere: frozenset[str] = frozenset()
    """Candidates already on another team for the same event."""

    def __post_init__(self) -> None:
        if not self.team:
            raise DomainValidationError("the existing team must contain at least one member")
        ids = [c.user_id for c in self.candidates]
        if len(set(ids)) != len(ids):
            raise DomainValidationError("duplicate candidate ids")
