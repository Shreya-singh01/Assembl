"""Semantic relevance f_sem (paper Eq. 1) and the texts it is computed from.

f_sem indicates topical relatedness only. It is not a proficiency estimate, a
compatibility measure or a probability of success.
"""

from __future__ import annotations

import math
from typing import Sequence

from .models import ProjectSpec, StudentProfile

TEXT_TEMPLATE_VERSION = "v1"
MAX_TEXT_CHARS = 4000


def profile_text(profile: StudentProfile) -> str:
    """Concatenation of skills, interests, preferred roles and project summaries
    (paper Section 4.2). Proficiency numbers are deliberately excluded."""
    parts: list[str] = []
    if profile.skills:
        parts.append("Skills: " + ", ".join(sorted(profile.skills, key=str.casefold)) + ".")
    if profile.interests:
        parts.append("Interests: " + ", ".join(profile.interests) + ".")
    roles = [*profile.primary_roles, *profile.secondary_roles]
    if roles:
        parts.append("Preferred roles: " + ", ".join(roles) + ".")
    summaries = [s.strip() for s in profile.project_summaries if s.strip()]
    if summaries:
        parts.append("Projects: " + " ".join(s if s.endswith(".") else s + "." for s in summaries))
    return " ".join(parts)[:MAX_TEXT_CHARS]


def project_text(project: ProjectSpec) -> str:
    """Project description combined with the required skills."""
    desc = " ".join(project.description.split())
    skills = ", ".join(r.skill for r in project.requirements)
    title = f"{project.title.strip()}. " if project.title.strip() else ""
    return f"{title}{desc} Required skills: {skills}."[:MAX_TEXT_CHARS]


def cosine_clipped(a: Sequence[float], b: Sequence[float]) -> float:
    """max(0, cos(a, b)). Zero or non-finite vectors yield 0.0."""
    if len(a) != len(b):
        raise ValueError(f"embedding dimensions differ: {len(a)} vs {len(b)}")
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if not (math.isfinite(dot) and math.isfinite(na) and math.isfinite(nb)) or na == 0 or nb == 0:
        return 0.0
    return min(1.0, max(0.0, dot / math.sqrt(na * nb)))
