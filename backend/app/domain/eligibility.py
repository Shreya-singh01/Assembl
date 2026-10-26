"""Mandatory eligibility filter E(c, P, T) (paper Section 4.4).

Applied before any scoring; ineligible candidates are never ranked. Each
decision carries structured reason codes.

A rule that cannot be checked because the candidate left the relevant field
blank produces an ``*_UNVERIFIED`` code, never a ``*_NOT_MET`` code: unknown
information is not treated as confirmed failure. The project's
``unverifiable_policy`` decides what happens next:

* ``exclude`` (default) - the candidate is not ranked, because the creator asked
  for the rule to be *satisfied* and it cannot be shown to be;
* ``include`` - the candidate is ranked and the unverified rule is flagged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence

from .features import TeamSlots, availability_overlap
from .models import ProjectSpec, StudentProfile


class Reason(str, Enum):
    PROFILE_HIDDEN = "PROFILE_HIDDEN"
    ALREADY_MEMBER = "ALREADY_MEMBER"
    COMMITTED_TO_EVENT_TEAM = "COMMITTED_TO_EVENT_TEAM"
    YEAR_NOT_ALLOWED = "YEAR_NOT_ALLOWED"
    YEAR_UNVERIFIED = "YEAR_UNVERIFIED"
    MANDATORY_SKILL_NOT_MET = "MANDATORY_SKILL_NOT_MET"
    MANDATORY_SKILL_UNVERIFIED = "MANDATORY_SKILL_UNVERIFIED"
    ROLE_NOT_MATCHED = "ROLE_NOT_MATCHED"
    ROLE_UNVERIFIED = "ROLE_UNVERIFIED"
    AVAILABILITY_NOT_MET = "AVAILABILITY_NOT_MET"
    AVAILABILITY_UNVERIFIED = "AVAILABILITY_UNVERIFIED"


REASON_TEXT = {
    Reason.PROFILE_HIDDEN: "Profile is hidden",
    Reason.ALREADY_MEMBER: "Already a member of this team",
    Reason.COMMITTED_TO_EVENT_TEAM: "Already on another team for the same event",
    Reason.YEAR_NOT_ALLOWED: "Year of study is outside the allowed years",
    Reason.YEAR_UNVERIFIED: "Year of study not stated",
    Reason.MANDATORY_SKILL_NOT_MET: "States a required skill below the mandatory level (or explicitly not at all)",
    Reason.MANDATORY_SKILL_UNVERIFIED: "Does not state a mandatory skill",
    Reason.ROLE_NOT_MATCHED: "Does not prefer any vacant role",
    Reason.ROLE_UNVERIFIED: "Preferred roles not stated",
    Reason.AVAILABILITY_NOT_MET: "Fewer shared weekly slots than the mandatory minimum",
    Reason.AVAILABILITY_UNVERIFIED: "Weekly availability not stated",
}

UNVERIFIED = {
    Reason.YEAR_UNVERIFIED,
    Reason.MANDATORY_SKILL_UNVERIFIED,
    Reason.ROLE_UNVERIFIED,
    Reason.AVAILABILITY_UNVERIFIED,
}


@dataclass(frozen=True)
class ReasonItem:
    code: Reason
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": REASON_TEXT[self.code], "detail": self.detail}


@dataclass(frozen=True)
class EligibilityDecision:
    candidate_id: str
    eligible: bool
    failures: tuple[ReasonItem, ...] = ()
    """Rules that were checked and not met (or excluded unverified rules)."""
    unverified: tuple[ReasonItem, ...] = ()
    """Rules that could not be checked. Under the ``include`` policy these
    candidates stay eligible and the items are surfaced as flags."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "eligible": self.eligible,
            "failures": [r.to_dict() for r in self.failures],
            "unverified": [r.to_dict() for r in self.unverified],
        }


def check_eligibility(
    project: ProjectSpec,
    team: Sequence[StudentProfile],
    candidate: StudentProfile,
    slots: TeamSlots,
    committed_elsewhere: frozenset[str] = frozenset(),
) -> EligibilityDecision:
    hard: list[ReasonItem] = []
    unverified: list[ReasonItem] = []

    if not candidate.visible:
        hard.append(ReasonItem(Reason.PROFILE_HIDDEN))
    if any(m.user_id == candidate.user_id for m in team):
        hard.append(ReasonItem(Reason.ALREADY_MEMBER))
    if candidate.user_id in committed_elsewhere:
        hard.append(ReasonItem(Reason.COMMITTED_TO_EVENT_TEAM))

    if project.allowed_years is not None:
        if candidate.year is None:
            unverified.append(ReasonItem(Reason.YEAR_UNVERIFIED))
        elif candidate.year not in project.allowed_years:
            hard.append(ReasonItem(Reason.YEAR_NOT_ALLOWED, {"year": candidate.year}))

    for req in project.requirements:
        if not req.mandatory:
            continue
        status = candidate.skill_status(req.skill)
        if status == "unknown":
            unverified.append(ReasonItem(Reason.MANDATORY_SKILL_UNVERIFIED, {"skill": req.skill}))
        elif candidate.proficiency(req.skill) < req.desired_proficiency:
            hard.append(
                ReasonItem(
                    Reason.MANDATORY_SKILL_NOT_MET,
                    {"skill": req.skill, "stated": candidate.skills.get(req.skill, 0), "required": req.desired_proficiency},
                )
            )

    if project.role_mandatory:
        if not candidate.primary_roles and not candidate.secondary_roles:
            unverified.append(ReasonItem(Reason.ROLE_UNVERIFIED))
        elif not (project.vacant_role_keys & (candidate.primary_role_keys | candidate.secondary_role_keys)):
            hard.append(ReasonItem(Reason.ROLE_NOT_MATCHED))

    # When no current member has stated availability the rule cannot be applied
    # at all; the engine reports that as a request-level warning instead.
    if project.availability_mandatory and slots.slots is not None:
        overlap = availability_overlap(candidate, slots)
        if overlap is None:
            unverified.append(ReasonItem(Reason.AVAILABILITY_UNVERIFIED))
        elif overlap < project.min_shared_slots:
            hard.append(
                ReasonItem(Reason.AVAILABILITY_NOT_MET, {"overlap": overlap, "required": project.min_shared_slots})
            )

    if project.unverifiable_policy == "exclude":
        failures = (*hard, *unverified)
        return EligibilityDecision(candidate.user_id, not failures, tuple(failures), tuple(unverified))
    return EligibilityDecision(candidate.user_id, not hard, tuple(hard), tuple(unverified))
