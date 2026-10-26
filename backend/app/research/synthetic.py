"""Synthetic scenario generator for local testing and demonstrations.

EVERYTHING produced here is synthetic: the students, the projects and - when
``simulate_judgments`` is on - the ratings. Simulated ratings come from a
hand-written rule over hidden variables. That rule partly overlaps with what
Assembl's features measure, so results on simulated ratings are circular and
say nothing about how well any method agrees with real students. They exist
only to exercise the evaluation pipeline end to end.
"""

from __future__ import annotations

import random
from typing import Any

SLOTS = [f"{d}-{p}" for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun") for p in ("am", "pm", "eve")]
ROLES = ["Frontend", "Backend", "ML", "Data", "Designer", "Mobile", "DevOps", "Presenter", "Researcher", "Hardware"]

ARCHETYPES: dict[str, dict[str, Any]] = {
    "frontend": {"role": "Frontend", "skills": ["React", "JavaScript", "TypeScript", "CSS", "HTML", "Tailwind CSS", "Next.js"],
                 "interests": ["web development", "user interfaces"],
                 "projects": ["Built a responsive React dashboard", "Made a portfolio site with Next.js"]},
    "backend": {"role": "Backend", "skills": ["Node.js", "Express.js", "PostgreSQL", "MongoDB", "REST API Development", "Django", "Database Design", "Docker"],
                "interests": ["backend systems", "databases"],
                "projects": ["Designed a REST API with Node.js and PostgreSQL", "Built a Django inventory service"]},
    "ml": {"role": "ML", "skills": ["Python", "Machine Learning", "Deep Learning", "PyTorch", "scikit-learn", "Pandas", "Natural Language Processing", "Computer Vision"],
           "interests": ["machine learning", "AI for health"],
           "projects": ["Trained an image classifier", "Built a sentiment analysis model"]},
    "data": {"role": "Data", "skills": ["Python", "SQL", "Data Analysis", "Data Visualization", "Pandas"],
             "interests": ["analytics", "dashboards"],
             "projects": ["Analysed placement statistics", "Built a Tableau-style dashboard"]},
    "design": {"role": "Designer", "skills": ["Figma", "UI Design", "UX Research", "Graphic Design"],
               "interests": ["product design", "accessibility"],
               "projects": ["Redesigned the college fest app", "Ran usability tests for a startup"]},
    "mobile": {"role": "Mobile", "skills": ["Flutter", "Dart", "Firebase", "React Native", "Kotlin", "Android Development"],
               "interests": ["mobile apps", "fintech"],
               "projects": ["Shipped a Flutter expense tracker", "Built an Android attendance app"]},
    "devops": {"role": "DevOps", "skills": ["Docker", "Kubernetes", "AWS", "Linux", "CI/CD", "Go"],
               "interests": ["cloud infrastructure", "developer tools"],
               "projects": ["Set up CI/CD for a club website", "Deployed microservices on Kubernetes"]},
    "presenter": {"role": "Presenter", "skills": ["Public Speaking", "Market Research", "Business Strategy", "Product Management", "Technical Writing"],
                  "interests": ["entrepreneurship", "pitching"],
                  "projects": ["Pitched at the e-cell startup weekend", "Wrote the hackathon project report"]},
    "hardware": {"role": "Hardware", "skills": ["Arduino", "Embedded Systems", "IoT", "C", "C++"],
                 "interests": ["robotics", "smart devices"],
                 "projects": ["Built an IoT soil-moisture monitor", "Programmed a line-following robot"]},
    "research": {"role": "Researcher", "skills": ["Research Writing", "Python", "Natural Language Processing", "Data Analysis", "PyTorch"],
                 "interests": ["NLP research", "academic writing"],
                 "projects": ["Co-authored a workshop paper", "Reproduced a transformer paper"]},
}

BASE_PROJECTS: list[dict[str, Any]] = [
    {"id": "P01", "title": "Placement-prep platform", "archetypes": ["frontend", "ml"],
     "description": "A web application that helps students prepare for campus placements with mock tests, interview practice and progress analytics.",
     "requirements": [("React", 2, 3), ("Node.js", 3, 3), ("PostgreSQL", 3, 2), ("Machine Learning", 2, 2), ("UI Design", 1, 2)],
     "roles": ["Backend", "Designer"]},
    {"id": "P02", "title": "Health-risk hackathon", "archetypes": ["ml", "data"],
     "description": "A 36-hour hackathon project predicting health risks from wearable data, with a clinician-facing dashboard and a final pitch.",
     "requirements": [("Machine Learning", 3, 3), ("Python", 3, 3), ("Data Visualization", 2, 2), ("React", 1, 2), ("Public Speaking", 2, 2)],
     "roles": ["Frontend", "Presenter"]},
    {"id": "P03", "title": "Student fintech app", "archetypes": ["mobile", "presenter"],
     "description": "A mobile app for shared student expenses with UPI-style settlement, built for an innovation challenge.",
     "requirements": [("Flutter", 3, 3), ("Firebase", 2, 2), ("UI Design", 2, 2), ("Node.js", 2, 2), ("Market Research", 1, 2)],
     "roles": ["Mobile", "Designer", "Backend"]},
    {"id": "P04", "title": "Smart-campus IoT", "archetypes": ["hardware", "data"],
     "description": "Sensors that monitor classroom occupancy and energy use, with a data pipeline and a demo for the department showcase.",
     "requirements": [("Arduino", 3, 2), ("Embedded Systems", 3, 3), ("Python", 2, 2), ("Data Analysis", 1, 2), ("Public Speaking", 2, 2)],
     "roles": ["Hardware", "Data"]},
    {"id": "P05", "title": "Code-mixed NLP paper", "archetypes": ["research", "ml"],
     "description": "A research paper on sentiment analysis for Hindi-English code-mixed text, targeting a student research workshop.",
     "requirements": [("Natural Language Processing", 3, 3), ("PyTorch", 3, 3), ("Research Writing", 3, 3), ("Data Analysis", 2, 2)],
     "roles": ["Researcher", "ML"]},
    {"id": "P06", "title": "Cloud deploy toolkit", "archetypes": ["devops", "frontend"],
     "description": "An open-source developer tool that previews pull requests on ephemeral cloud environments, built for a semester project.",
     "requirements": [("Docker", 3, 3), ("Kubernetes", 2, 2), ("CI/CD", 2, 2), ("Node.js", 2, 3), ("React", 1, 2)],
     "roles": ["Backend", "DevOps"]},
]


def _student(rng: random.Random, uid: str, archetype: str) -> dict[str, Any]:
    a = ARCHETYPES[archetype]
    k = rng.randint(2, min(5, len(a["skills"])))
    skills = {s: rng.choices([1, 2, 3, 4], weights=[2, 4, 4, 2])[0] for s in rng.sample(a["skills"], k)}
    if rng.random() < 0.35:  # a cross-over skill from another archetype
        other = ARCHETYPES[rng.choice([x for x in ARCHETYPES if x != archetype])]
        skills.setdefault(rng.choice(other["skills"]), rng.randint(1, 3))
    secondary_pool = [r for r in ROLES if r != a["role"]]
    profile: dict[str, Any] = {
        "user_id": uid,
        "skills": skills,
        "year": rng.randint(1, 4),
        "branch": rng.choice(["CSE", "IT", "AI-DS", "ECE", "MAE"]),
        "primary_roles": [a["role"]] if rng.random() > 0.08 else [],
        "secondary_roles": rng.sample(secondary_pool, rng.randint(0, 1)),
        "interests": list(a["interests"]),
        "project_summaries": rng.sample(a["projects"], rng.randint(0, 2)),
        "availability": sorted(rng.sample(SLOTS, rng.randint(2, 9))) if rng.random() > 0.2 else None,
        "weekly_hours": rng.choice([4, 6, 8, 10, 12, 15, 20]) if rng.random() > 0.1 else None,
        "work_mode": rng.choice(["online", "offline", "hybrid"]) if rng.random() > 0.1 else None,
        "_archetype": archetype,
        # hidden "true" proficiency inflation, used only by the simulated raters
        "_inflation": rng.choice([0, 0, 0, 1]),
    }
    return profile


def _public(p: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in p.items() if not k.startswith("_")}


def _simulated_rating(rng: random.Random, project: dict, team: list[dict], cand: dict, rater_bias: float) -> int:
    def true(p: dict, s: str) -> int:
        return max(0, p["skills"].get(s, 0) - p.get("_inflation", 0))

    reqs = project["requirements"]
    total = sum(r["importance"] for r in reqs)
    need = 0.0
    for r in reqs:
        best = max((true(m, r["skill"]) for m in team), default=0)
        before = min(1, best / r["desired_proficiency"])
        after = min(1, max(best, true(cand, r["skill"])) / r["desired_proficiency"])
        need += r["importance"] * (after - before)
    need /= total
    role = 1.0 if set(cand["primary_roles"]) & set(project["vacant_roles"]) else 0.0
    avail = 0.0
    if project["synchronous"] and cand.get("availability") is not None:
        team_slots = set.intersection(*[set(m["availability"]) for m in team if m.get("availability")] or [set()])
        avail = 1.0 if len(set(cand["availability"]) & team_slots) >= project["min_shared_slots"] else -0.5
    relevance = 0.4 if cand["_archetype"] in project["_archetypes_relevant"] else 0.0
    u = 3.2 * need + 0.6 * role + 0.4 * avail + relevance + rater_bias + rng.gauss(0, 0.45)
    return int(min(3, max(0, round(u))))


def generate(seed: int = 42, per_project: int = 5, pool_size: int = 24, population: int = 160,
             simulate_judgments: bool = True, raters: int = 3) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    arche = list(ARCHETYPES)
    people = [_student(rng, f"syn-u{i:03d}", arche[i % len(arche)]) for i in range(population)]
    by_arch: dict[str, list[dict]] = {a: [p for p in people if p["_archetype"] == a] for a in arche}
    used_as_member: set[str] = set()
    scenarios: list[dict[str, Any]] = []
    team_sizes = [1, 1, 2, 2, 3]
    for bp in BASE_PROJECTS:
        # team members are drawn from a project-specific reserve, so the only
        # leakage link between scenarios is the base project itself
        reserve = [p for a in bp["archetypes"] for p in by_arch[a] if p["user_id"] not in used_as_member][:6]
        used_as_member.update(p["user_id"] for p in reserve)
        for v in range(per_project):
            size = team_sizes[v % len(team_sizes)]
            team = rng.sample(reserve, size)
            sync = v % 2 == 1
            for m in team:  # synchronous teams need some shared availability
                if sync and m.get("availability") is None:
                    m["availability"] = sorted(rng.sample(SLOTS, 6))
            if sync:
                anchor = rng.sample(SLOTS, 4)
                for m in team:
                    m["availability"] = sorted(set(m["availability"]) | set(anchor))
            reqs = [{"skill": s, "importance": a, "desired_proficiency": r, "mandatory": False}
                    for s, a, r in bp["requirements"]]
            if v == 4:
                reqs[0]["mandatory"] = True
            project = {
                "project_id": f"{bp['id']}-v{v + 1}",
                "title": bp["title"],
                "description": bp["description"],
                "requirements": reqs,
                "target_size": size + rng.randint(1, 3),
                "vacant_roles": bp["roles"],
                "allowed_years": [2, 3, 4] if v == 3 else None,
                "synchronous": sync,
                "min_shared_slots": 2 if sync else 0,
                "availability_policy": "all",
                "availability_mandatory": False,
                "weekly_hours": rng.choice([6, 8, 10, 12]),
                "work_mode": rng.choice(["online", "offline", "hybrid"]),
                "unverifiable_policy": "exclude",
            }
            member_ids = {m["user_id"] for m in team}
            pool = rng.sample([p for p in people if p["user_id"] not in member_ids and p["user_id"] not in used_as_member],
                              pool_size)
            sid = f"SYN-{bp['id']}-{v + 1}"
            scen: dict[str, Any] = {
                "scenario_id": sid,
                "base_project_id": bp["id"],
                "provenance": "synthetic",
                "notes": "Synthetic scenario generated by app.research.synthetic; not real student data.",
                "project": project,
                "team": [_public(m) for m in team],
                "candidates": [_public(c) for c in pool],
                "judgments": [],
                "judgment_provenance": "none",
            }
            if simulate_judgments:
                proj_view = {**project, "_archetypes_relevant": set(bp["archetypes"]) | {
                    a for a, spec in ARCHETYPES.items() if spec["role"] in bp["roles"]}}
                for r in range(raters):
                    bias = rng.gauss(0, 0.25)
                    for c in pool:
                        scen["judgments"].append({
                            "rater_id": f"sim-rater-{r + 1}", "candidate_id": c["user_id"],
                            "rating": _simulated_rating(rng, proj_view, team, c, bias)})
                scen["judgment_provenance"] = "simulated"
                scen["notes"] += " Ratings are SIMULATED by a rule, not human judgments; results on them are not evidence."
            scenarios.append(scen)
    return scenarios
