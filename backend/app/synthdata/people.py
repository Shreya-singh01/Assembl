"""Synthetic student profiles with guaranteed edge-case coverage.

Edge cases are assigned by fixed quota (not left to chance), so every run of
the same size contains every case. Student 0 is always a complete, visible
frontend profile ("Aarav"): demo logins and the browser tests rely on it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from app.domain.skills import default_registry
from app.research.synthetic import ARCHETYPES, SLOTS

FIRST = [
    "Aarav", "Diya", "Kabir", "Meera", "Rohan", "Sana", "Ishaan", "Tara", "Vivaan", "Anaya", "Arjun", "Zoya",
    "Neel", "Riya", "Dev", "Kiara", "Yash", "Ira", "Kunal", "Nisha", "Om", "Pari", "Reyansh", "Siya", "Aditya",
    "Bhavya", "Chirag", "Divya", "Eshan", "Fatima", "Gaurav", "Harini", "Imran", "Jasleen", "Karthik", "Lavanya",
    "Manav", "Nandini", "Ojas", "Prisha", "Qasim", "Rhea", "Samar", "Tanvi", "Uday", "Vanya", "Wasim", "Yamini",
    "Zara", "Aisha", "Bilal", "Charvi", "Darsh", "Eva", "Farhan", "Gauri", "Hriday", "Ishita", "Jai", "Kavya",
]
LAST = [
    "Sharma", "Verma", "Iyer", "Khan", "Reddy", "Gupta", "Nair", "Singh", "Das", "Mehta", "Kapoor", "Joshi",
    "Bose", "Patel", "Rao", "Chopra", "Menon", "Malhotra", "Pillai", "Ahmed", "Banerjee", "Kulkarni", "Saxena",
    "Fernandes", "Thakur", "Mishra", "Agarwal", "Sethi", "Chauhan", "Ghosh",
]
BRANCHES = ["CSE", "IT", "AI-DS", "ECE", "MAE", "EEE", "AI-ML", "BBA"]
GENERAL_INTERESTS = ["open source", "hackathons", "edtech", "sustainability", "healthcare", "fintech",
                     "social impact", "gaming", "accessibility", "startups", "competitive programming"]
NON_TECHNICAL = {"Public Speaking", "Market Research", "Business Strategy", "Product Management",
                 "Technical Writing", "Research Writing", "Project Management", "UX Research", "Video Editing"}
UNRECOGNISED = ["Godot", "LaTeX", "Notion", "Canva", "Blender", "Elm"]
PROJECT_DETAIL = {
    "frontend": ("Built the UI and state management", "Implemented responsive pages and component library"),
    "backend": ("Designed the database schema and APIs", "Wrote the REST endpoints and authentication"),
    "ml": ("Trained and evaluated the models", "Handled data cleaning and feature engineering"),
    "data": ("Built the analysis notebooks and dashboard", "Cleaned survey data and ran the statistics"),
    "design": ("Ran user interviews and made the prototypes", "Designed the visual system in Figma"),
    "mobile": ("Built the Flutter app screens", "Integrated Firebase auth and push notifications"),
    "devops": ("Set up CI/CD and deployment", "Containerised the services with Docker"),
    "presenter": ("Led the pitch and market research", "Wrote the report and handled the demo day"),
    "hardware": ("Wired the sensors and wrote the firmware", "Built the prototype and power circuit"),
    "research": ("Wrote the literature review and paper", "Ran the experiments and wrote the results"),
}

# Edge-case quotas as a share of all students (index 0 is always "complete").
QUOTAS = [
    ("availability_not_stated", 0.15),
    ("availability_stated_none", 0.03),
    ("hours_not_stated", 0.08),
    ("mode_not_stated", 0.08),
    ("roles_not_stated", 0.05),
    ("no_skills", 0.02),
    ("year_not_stated", 0.04),
    ("hidden", 0.08),
    ("declared_absent", 0.10),
    ("unrecognised_skill", 0.06),
    ("duplicate_skill_spellings", 0.04),
    ("few_projects_listed", 0.10),
]


@dataclass
class StudentPlan:
    index: int
    first: str
    last: str
    handle: str
    archetype: str
    cases: set[str]
    profile: dict[str, Any]  # ProfileIn-compatible payload (labels as a student would type them)
    canonical_skills: dict[str, int] = field(default_factory=dict)

    @property
    def visible(self) -> bool:
        return self.profile["visible"]

    @property
    def availability(self) -> set[str] | None:
        a = self.profile["availability"]
        return None if a is None else set(a)

    @property
    def primary_roles(self) -> list[str]:
        return self.profile["primary_roles"]


def _aliases_by_canonical() -> dict[str, list[str]]:
    reg = default_registry()
    out: dict[str, list[str]] = {}
    for alias, canonical in reg._alias.items():  # explicit aliases only
        out.setdefault(canonical, []).append(alias)
    return out


def _availability(rng: random.Random) -> list[str]:
    style = rng.choice(["evenings", "weekends", "mixed", "mornings", "busy"])
    if style == "evenings":
        pool = [s for s in SLOTS if s.endswith("eve")]
    elif style == "weekends":
        pool = [s for s in SLOTS if s.startswith(("sat", "sun"))]
    elif style == "mornings":
        pool = [s for s in SLOTS if s.endswith("am")]
    else:
        pool = SLOTS
    k = 2 if style == "busy" else rng.randint(3, min(9, len(pool)))
    return sorted(rng.sample(pool, k))


def assign_cases(n: int, rng: random.Random) -> list[set[str]]:
    cases: list[set[str]] = [set() for _ in range(n)]
    eligible = list(range(1, n))
    for name, share in QUOTAS:
        k = max(1, round(share * n))
        for i in rng.sample(eligible, min(k, len(eligible))):
            cases[i].add(name)
    for c in cases:  # keep combinations coherent
        if "no_skills" in c:
            c -= {"unrecognised_skill", "duplicate_skill_spellings", "declared_absent"}
        if "availability_not_stated" in c:
            c.discard("availability_stated_none")
    return cases


def make_students(n: int, seed: int = 11) -> list[StudentPlan]:
    rng = random.Random(seed)
    archetypes = list(ARCHETYPES)
    aliases = _aliases_by_canonical()
    reg = default_registry()
    cases = assign_cases(n, rng)
    students: list[StudentPlan] = []
    for i in range(n):
        first = FIRST[i % len(FIRST)]
        last = LAST[(i * 7) % len(LAST)]
        arch = archetypes[i % len(archetypes)]
        spec = ARCHETYPES[arch]
        c = cases[i]
        handle = f"{first.lower()}_demo{i}"

        skills: list[dict[str, Any]] = []
        if "no_skills" not in c:
            picked = rng.sample(spec["skills"], rng.randint(3, min(6, len(spec["skills"]))))
            if rng.random() < 0.5:  # a cross-over skill from another archetype
                other = ARCHETYPES[rng.choice([a for a in archetypes if a != arch])]
                extra = rng.choice(other["skills"])
                if extra not in picked:
                    picked.append(extra)
            for s in picked:
                level = rng.choices([1, 2, 3, 4], weights=[2, 4, 4, 2])[0]
                label = s
                if s in aliases and rng.random() < 0.25:  # typed as a common variant, e.g. "nodejs"
                    label = rng.choice(aliases[s])
                skills.append({"label": label, "proficiency": level,
                               "kind": "non_technical" if s in NON_TECHNICAL else "technical"})
            if "duplicate_skill_spellings" in c and skills:
                s0 = skills[0]
                canonical = reg.normalize(s0["label"]).canonical
                variant = (aliases.get(canonical) or [canonical.lower()])[0]
                skills.append({"label": variant, "proficiency": max(1, s0["proficiency"] - 1), "kind": s0["kind"]})
            if "unrecognised_skill" in c:
                skills.append({"label": rng.choice(UNRECOGNISED), "proficiency": rng.randint(1, 3), "kind": "technical"})

        declared_absent: list[str] = []
        if "declared_absent" in c:
            stated = {reg.normalize(s["label"]).canonical for s in skills}
            other_skills = [s for a in archetypes if a != arch for s in ARCHETYPES[a]["skills"] if s not in stated]
            declared_absent = sorted(set(rng.sample(other_skills, 2)))

        role = spec["role"]
        secondary_pool = [ARCHETYPES[a]["role"] for a in archetypes if ARCHETYPES[a]["role"] != role]
        if "roles_not_stated" in c:
            primary, secondary = [], []
        else:
            primary, secondary = [role], rng.sample(secondary_pool, rng.randint(0, 2))

        n_projects = 0 if "few_projects_listed" in c else rng.randint(1, 3)
        projects = []
        for title in rng.sample(spec["projects"], min(n_projects, len(spec["projects"]))):
            summary, contribution = PROJECT_DETAIL[arch]
            projects.append({"title": title, "summary": f"{title} for a college club or course.",
                             "contribution": rng.choice([summary, contribution]),
                             "link": f"https://github.com/{handle}/{title.split()[0].lower()}-project"})

        if "availability_not_stated" in c:
            availability = None
        elif "availability_stated_none" in c:
            availability = []
        else:
            availability = _availability(rng)

        profile = {
            "year": None if "year_not_stated" in c else rng.choices([1, 2, 3, 4, 5], weights=[2, 4, 4, 3, 1])[0],
            "branch": rng.choice(BRANCHES),
            "skills": skills,
            "declared_absent": declared_absent,
            "primary_roles": primary,
            "secondary_roles": secondary,
            "interests": list(spec["interests"]) + rng.sample(GENERAL_INTERESTS, rng.randint(0, 2)),
            "projects": projects,
            "links": [f"https://github.com/{handle}"] if rng.random() < 0.6 else [],
            "availability": availability,
            "weekly_hours": None if "hours_not_stated" in c else rng.choice([4, 6, 8, 10, 12, 15, 20]),
            "work_mode": None if "mode_not_stated" in c else rng.choice(["online", "offline", "hybrid", "hybrid"]),
            "visible": "hidden" not in c,
        }
        canonical = {}
        for s in skills:
            k = reg.normalize(s["label"]).canonical
            canonical[k] = max(canonical.get(k, 0), s["proficiency"])
        students.append(StudentPlan(i, first, last, handle, arch, c, profile, canonical))
    return students
