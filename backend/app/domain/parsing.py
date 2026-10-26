"""Build domain objects from plain dicts (stored documents, scenario files).

Skill labels pass through the alias registry here, so every caller sees
canonical labels.
"""

from __future__ import annotations

from typing import Any, Mapping

from .models import ProjectSpec, Requirement, StudentProfile
from .skills import SkillRegistry, default_registry


def _skills_from(raw: Any, registry: SkillRegistry) -> dict[str, int]:
    if not raw:
        return {}
    if isinstance(raw, Mapping):
        items = list(raw.items())
    else:  # [{"label"|"skill": ..., "proficiency": ...}]
        items = [(s.get("label") or s.get("skill"), s["proficiency"]) for s in raw]
    skills, _, _ = registry.normalize_proficiencies(items)
    return skills


def profile_from_dict(d: Mapping[str, Any], registry: SkillRegistry | None = None) -> StudentProfile:
    registry = registry or default_registry()
    skills = _skills_from(d.get("skills"), registry)
    absent = frozenset(registry.normalize_labels(d.get("declared_absent") or [])) - set(skills)
    availability = d.get("availability")
    return StudentProfile(
        user_id=str(d["user_id"]),
        skills=skills,
        declared_absent=absent,
        year=d.get("year"),
        branch=d.get("branch"),
        primary_roles=tuple(d.get("primary_roles") or ()),
        secondary_roles=tuple(d.get("secondary_roles") or ()),
        interests=tuple(d.get("interests") or ()),
        project_summaries=tuple(d.get("project_summaries") or ()),
        availability=None if availability is None else frozenset(availability),
        weekly_hours=d.get("weekly_hours"),
        work_mode=d.get("work_mode"),
        visible=d.get("visible", True),
    )


def requirement_from_dict(d: Mapping[str, Any], registry: SkillRegistry) -> Requirement:
    return Requirement(
        skill=registry.normalize(d["skill"]).canonical,
        importance=int(d["importance"]),
        desired_proficiency=int(d["desired_proficiency"]),
        mandatory=bool(d.get("mandatory", False)),
    )


def project_from_dict(d: Mapping[str, Any], registry: SkillRegistry | None = None) -> ProjectSpec:
    registry = registry or default_registry()
    years = d.get("allowed_years")
    return ProjectSpec(
        project_id=str(d["project_id"]),
        title=d.get("title", ""),
        description=d.get("description", ""),
        requirements=tuple(requirement_from_dict(r, registry) for r in d.get("requirements", [])),
        target_size=int(d["target_size"]),
        vacant_roles=tuple(d.get("vacant_roles") or ()),
        allowed_years=frozenset(years) if years else None,
        role_mandatory=bool(d.get("role_mandatory", False)),
        synchronous=bool(d.get("synchronous", False)),
        min_shared_slots=int(d.get("min_shared_slots") or 0),
        availability_policy=d.get("availability_policy", "all"),
        availability_mandatory=bool(d.get("availability_mandatory", False)),
        weekly_hours=d.get("weekly_hours"),
        work_mode=d.get("work_mode"),
        unverifiable_policy=d.get("unverifiable_policy", "exclude"),
    )
