"""Collaboration features f_role, f_avail and f_work (paper Section 4.4).

Each feature returns a :class:`FeatureValue`. ``value is None`` means the
feature is *omitted for the whole request* (its weight is redistributed);
a per-candidate unknown instead receives a neutral 0.5 that is flagged.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from .models import HOURS_MAX, HOURS_MIN, ProjectSpec, StudentProfile, role_key

NEUTRAL = 0.5
H_MAX = HOURS_MAX - HOURS_MIN  # largest possible difference on the form

Status = Literal["computed", "neutral_unknown", "omitted"]


@dataclass(frozen=True)
class FeatureValue:
    value: float | None
    status: Status
    detail: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def omitted(cls, reason: str, **detail: Any) -> "FeatureValue":
        return cls(None, "omitted", {"reason": reason, **detail})


# --- f_role -----------------------------------------------------------------

def role_fit(project: ProjectSpec, candidate: StudentProfile) -> FeatureValue:
    """1 if a vacant role is a primary preference, 0.5 if secondary, else 0.

    With several vacant roles the best match is used (a candidate needs to fit
    only one of them). Omitted when the team lists no vacant roles."""
    vacant = project.vacant_role_keys
    if not vacant:
        return FeatureValue.omitted("no_vacant_roles")
    labels = {role_key(r): r for r in project.vacant_roles}
    primary = sorted(vacant & candidate.primary_role_keys)
    if primary:
        return FeatureValue(1.0, "computed", {"match": "primary", "role": labels.get(primary[0], primary[0])})
    secondary = sorted(vacant & candidate.secondary_role_keys)
    if secondary:
        return FeatureValue(0.5, "computed", {"match": "secondary", "role": labels.get(secondary[0], secondary[0])})
    if not candidate.primary_roles and not candidate.secondary_roles:
        # Paper defines 0 for "otherwise"; we keep 0 but flag that roles were not stated.
        return FeatureValue(0.0, "computed", {"match": "none", "roles_stated": False})
    return FeatureValue(0.0, "computed", {"match": "none", "roles_stated": True})


# --- f_avail ----------------------------------------------------------------

@dataclass(frozen=True)
class TeamSlots:
    slots: frozenset[str] | None
    """A_T; None when no current member has stated availability."""
    members_with_availability: int
    members_total: int
    policy: str


def team_slots(project: ProjectSpec, team: Sequence[StudentProfile]) -> TeamSlots:
    known = [m.availability for m in team if m.availability is not None]
    if not known:
        return TeamSlots(None, 0, len(team), project.availability_policy)
    if project.availability_policy == "majority":
        counts = Counter(slot for slots in known for slot in slots)
        need = len(known) // 2 + 1
        shared = frozenset(s for s, n in counts.items() if n >= need)
    else:
        shared = frozenset.intersection(*known)
    return TeamSlots(shared, len(known), len(team), project.availability_policy)


def availability_overlap(candidate: StudentProfile, slots: TeamSlots) -> int | None:
    if candidate.availability is None or slots.slots is None:
        return None
    return len(candidate.availability & slots.slots)


def availability_fit(project: ProjectSpec, slots: TeamSlots, candidate: StudentProfile) -> FeatureValue:
    """f_avail = min(1, |A_c n A_T| / h); omitted for asynchronous teams."""
    if not project.synchronous:
        return FeatureValue.omitted("team_not_synchronous")
    if slots.slots is None:
        return FeatureValue.omitted("team_availability_not_stated")
    h = project.min_shared_slots
    base = {"team_slots": len(slots.slots), "required": h, "policy": slots.policy}
    if candidate.availability is None:
        return FeatureValue(NEUTRAL, "neutral_unknown", {**base, "overlap": None, "stated": False})
    overlap = len(candidate.availability & slots.slots)
    return FeatureValue(min(1.0, overlap / h), "computed", {**base, "overlap": overlap, "stated": True})


# --- f_work -----------------------------------------------------------------

def mode_compatibility(a: str, b: str) -> float:
    if a == b or "hybrid" in (a, b):
        return 1.0
    return 0.0


def work_fit(project: ProjectSpec, candidate: StudentProfile) -> FeatureValue:
    """Mean of commitment alignment 1 - |h_c - h_T| / H_max and working-mode
    compatibility. A component the project does not state is left out of the
    mean; a component the candidate does not state gets a flagged neutral 0.5.
    Omitted entirely when the project states neither hours nor mode."""
    parts: list[float] = []
    detail: dict[str, Any] = {"unknown": []}
    if project.weekly_hours is not None:
        if candidate.weekly_hours is None:
            parts.append(NEUTRAL)
            detail["unknown"].append("weekly_hours")
            detail["commitment"] = None
        else:
            diff = abs(candidate.weekly_hours - project.weekly_hours)
            commit = 1.0 - diff / H_MAX if H_MAX > 0 else (1.0 if diff == 0 else 0.0)
            commit = min(1.0, max(0.0, commit))
            parts.append(commit)
            detail["commitment"] = commit
            detail["hours"] = {"candidate": candidate.weekly_hours, "team": project.weekly_hours}
    if project.work_mode is not None:
        if candidate.work_mode is None:
            parts.append(NEUTRAL)
            detail["unknown"].append("work_mode")
            detail["mode"] = None
        else:
            m = mode_compatibility(candidate.work_mode, project.work_mode)
            parts.append(m)
            detail["mode"] = m
            detail["modes"] = {"candidate": candidate.work_mode, "team": project.work_mode}
    if not parts:
        return FeatureValue.omitted("team_states_no_commitment_or_mode")
    status: Status = "neutral_unknown" if detail["unknown"] else "computed"
    return FeatureValue(sum(parts) / len(parts), status, detail)
