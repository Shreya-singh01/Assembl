"""Explanations assembled from the scoring inputs and nothing else (paper Section 4.5).

The structured form is what the API returns; :func:`render_text` turns it into
a sentence such as "Adds PostgreSQL (essential; stated proficiency 3 of 4) ...".
Both are deterministic functions of the ranking inputs, so an explanation can
always be reproduced from them.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .coverage import EPS, CoverageReport
from .eligibility import ReasonItem
from .features import FeatureValue
from .models import IMPORTANCE_LABELS, PROFICIENCY_MAX, ProjectSpec, StudentProfile


def build_explanation(
    project: ProjectSpec,
    candidate: StudentProfile,
    before: CoverageReport,
    after: CoverageReport,
    gain: float,
    features: Mapping[str, FeatureValue],
    active_weights: Mapping[str, float],
    omitted: Mapping[str, str],
    renormalized: bool,
    unverified: Sequence[ReasonItem] = (),
) -> dict[str, Any]:
    before_by = before.by_skill()
    adds: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for s_after in after.per_skill:
        s_before = before_by[s_after.skill]
        status = candidate.skill_status(s_after.skill)
        item = {
            "skill": s_after.skill,
            "importance": s_after.importance,
            "importance_label": IMPORTANCE_LABELS[s_after.importance],
            "desired_proficiency": s_after.desired_proficiency,
            "candidate_proficiency": candidate.skills.get(s_after.skill),
            "candidate_status": status,
            "team_best_before": s_before.best_proficiency,
            "coverage_before": s_before.coverage,
            "coverage_after": s_after.coverage,
        }
        if s_after.coverage > s_before.coverage + EPS:
            item["fully_covers"] = s_after.coverage >= 1.0 - EPS
            adds.append(item)
        elif status == "stated":
            duplicates.append(item)
        if s_after.coverage < 1.0 - EPS:
            remaining.append(item)

    unknowns: list[str] = []
    if not candidate.skills:
        unknowns.append("No skills stated")
    avail = features.get("avail")
    if avail is not None and avail.status == "neutral_unknown":
        unknowns.append("Weekly availability not stated (neutral 0.5 used)")
    work = features.get("work")
    if work is not None and work.status == "neutral_unknown":
        for f in work.detail.get("unknown", []):
            unknowns.append(
                "Expected weekly hours not stated (neutral 0.5 used)" if f == "weekly_hours"
                else "Working mode not stated (neutral 0.5 used)"
            )
    role = features.get("role")
    if role is not None and role.value is not None and role.detail.get("roles_stated") is False:
        unknowns.append("Preferred roles not stated")
    unstated_required = [
        r.skill for r in project.requirements if candidate.skill_status(r.skill) == "unknown"
    ]

    contributions = {
        k: {"value": features[k].value, "weight": w, "contribution": w * (features[k].value or 0.0)}
        for k, w in active_weights.items()
    }
    return {
        "semantic_relevance": features["sem"].value,
        "team_coverage_before": before.overall,
        "team_coverage_after": after.overall,
        "added_coverage": gain,
        "adds": adds,
        "duplicates": duplicates,
        "remaining_gaps": remaining,
        "all_requirements_covered_before": before.complete,
        "required_skills_not_stated": unstated_required,
        "role": None if role is None else {"value": role.value, "status": role.status, **role.detail},
        "availability": None if avail is None else {"value": avail.value, "status": avail.status, **avail.detail},
        "work": None if work is None else {"value": work.value, "status": work.status, **work.detail},
        "contributions": contributions,
        "omitted_features": dict(omitted),
        "weights_renormalized": renormalized,
        "unknowns": unknowns,
        "unverified_rules": [u.to_dict() for u in unverified],
        "caveats": ["Proficiency is self-reported."],
    }


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def render_text(expl: Mapping[str, Any]) -> str:
    sentences: list[str] = []
    if expl["all_requirements_covered_before"]:
        sentences.append("All listed requirements are already met by the current team.")
    elif expl["adds"]:
        parts = [
            f"{a['skill']} ({a['importance_label']}; stated proficiency {a['candidate_proficiency']} of {PROFICIENCY_MAX}"
            + ("" if a["fully_covers"] else f", below the desired {a['desired_proficiency']}")
            + ")"
            for a in expl["adds"]
        ]
        sentences.append("Adds " + _join(parts) + ".")
    else:
        sentences.append("Does not add coverage of any listed requirement.")
    if expl["duplicates"] and not expl["all_requirements_covered_before"]:
        sentences.append("Repeats " + _join([d["skill"] for d in expl["duplicates"]]) + ", already covered by the team.")

    role = expl.get("role")
    if role and role.get("value") is not None:
        if role.get("match") == "primary":
            sentences.append(f"Prefers the vacant {role['role']} role.")
        elif role.get("match") == "secondary":
            sentences.append(f"Lists the vacant {role['role']} role as a secondary preference.")
        elif role.get("roles_stated") is False:
            sentences.append("Preferred roles not stated.")
        else:
            sentences.append("Does not prefer any vacant role.")

    avail = expl.get("availability")
    if avail and avail.get("value") is not None:
        if avail.get("stated"):
            sentences.append(f"Shares {avail['overlap']} of the team's {avail['team_slots']} weekly slots.")
        else:
            sentences.append("Availability not stated.")

    work = expl.get("work")
    if work and work.get("value") is not None:
        modes = work.get("modes")
        if modes and work.get("mode") == 0.0:
            sentences.append(f"Prefers working {modes['candidate']}; the team works {modes['team']}.")
        hours = work.get("hours")
        if hours and hours["candidate"] != hours["team"]:
            sentences.append(f"Expects {hours['candidate']} h/week against the team's {hours['team']} h/week.")

    if expl["remaining_gaps"] and not expl["all_requirements_covered_before"]:
        uncovered = [g["skill"] for g in expl["remaining_gaps"] if g["coverage_after"] <= EPS]
        partial = [g["skill"] for g in expl["remaining_gaps"] if g["coverage_after"] > EPS]
        if uncovered:
            sentences.append(_join(uncovered) + (" remains" if len(uncovered) == 1 else " remain") + " uncovered.")
        if partial:
            sentences.append(_join(partial) + (" remains" if len(partial) == 1 else " remain") + " below the desired level.")
    for u in expl["unverified_rules"]:
        sentences.append(f"Unverified rule: {u['message'].lower()}.")
    sentences.extend(expl["caveats"])
    return " ".join(sentences)
