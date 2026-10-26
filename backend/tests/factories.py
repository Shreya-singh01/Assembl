"""Small builders for domain objects used across tests."""

from __future__ import annotations

from app.domain.models import ProjectSpec, RecommendationRequest, Requirement, StudentProfile


def person(uid: str, skills: dict[str, int] | None = None, **kw) -> StudentProfile:
    for key in ("primary_roles", "secondary_roles", "interests", "project_summaries"):
        if key in kw:
            kw[key] = tuple(kw[key])
    if "availability" in kw and kw["availability"] is not None:
        kw["availability"] = frozenset(kw["availability"])
    if "declared_absent" in kw:
        kw["declared_absent"] = frozenset(kw["declared_absent"])
    return StudentProfile(user_id=uid, skills=skills or {}, **kw)


def req(skill: str, importance: int, desired: int, mandatory: bool = False) -> Requirement:
    return Requirement(skill, importance, desired, mandatory)


# Hand-checked fixture used throughout (paper Scenario A).
#   React a=2 r=3 | Machine Learning a=2 r=3 | Node.js a=3 r=3 | PostgreSQL a=3 r=2
#   sum a = 10; team covers React (3/3) and ML (min(1, 4/3)) -> Coverage(T) = 4/10 = 0.4
SCENARIO_A_REQS = (
    req("React", 2, 3),
    req("Machine Learning", 2, 3),
    req("Node.js", 3, 3),
    req("PostgreSQL", 3, 2),
)


def scenario_a_project(**kw) -> ProjectSpec:
    defaults = dict(
        project_id="p-a",
        title="Placement prep platform",
        description="A placement-preparation web application with mock interviews.",
        requirements=SCENARIO_A_REQS,
        target_size=4,
        vacant_roles=("Backend",),
    )
    defaults.update(kw)
    return ProjectSpec(**defaults)


def scenario_a_team() -> tuple[StudentProfile, ...]:
    return (
        person("alice", {"React": 3, "CSS": 3}, primary_roles=["Frontend"]),
        person("bob", {"Machine Learning": 4, "Python": 3}, primary_roles=["ML"]),
    )


def request(project: ProjectSpec, team, candidates, semantic: dict[str, float] | None = None, **kw):
    semantic = semantic or {c.user_id: 0.5 for c in candidates}
    return RecommendationRequest(project, tuple(team), tuple(candidates), semantic, **kw)
