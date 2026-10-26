"""Evaluation scenarios: project + requirements + existing team + candidate pool
+ (optionally) suitability judgments.

``provenance`` records where the scenario came from ("synthetic" or "real");
``judgment_provenance`` records where its ratings came from ("none",
"simulated" or "human"). Only ``real`` scenarios with ``human`` judgments can
support research claims; everything else is a pipeline demonstration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Literal

from app.domain.models import ProjectSpec, StudentProfile
from app.domain.parsing import profile_from_dict, project_from_dict
from app.domain.skills import SkillRegistry, default_registry

RATING_MIN, RATING_MAX = 0, 3
RATING_LABELS = {0: "not suitable", 1: "marginally suitable", 2: "suitable", 3: "strongly suitable"}

Provenance = Literal["synthetic", "real"]
JudgmentProvenance = Literal["none", "simulated", "human"]


@dataclass(frozen=True)
class Judgment:
    rater_id: str
    candidate_id: str
    rating: int

    def __post_init__(self) -> None:
        if not (RATING_MIN <= self.rating <= RATING_MAX) or isinstance(self.rating, bool):
            raise ValueError(f"rating must be {RATING_MIN}-{RATING_MAX}, got {self.rating!r}")


@dataclass
class Scenario:
    scenario_id: str
    base_project_id: str
    provenance: Provenance
    project: ProjectSpec
    team: tuple[StudentProfile, ...]
    candidates: tuple[StudentProfile, ...]
    judgments: list[Judgment] = field(default_factory=list)
    judgment_provenance: JudgmentProvenance = "none"
    committed_elsewhere: frozenset[str] = frozenset()
    notes: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def labels(self, restrict_to: set[str] | None = None) -> dict[str, float]:
        """Mean rating per judged candidate (the graded relevance label).
        Candidates without any rating are absent, never zero. Pass the eligible
        pool as ``restrict_to``: only eligible candidates are ever ranked, so
        the ideal ordering must not include ratings of excluded candidates."""
        by: dict[str, list[int]] = {}
        for j in self.judgments:
            if restrict_to is None or j.candidate_id in restrict_to:
                by.setdefault(j.candidate_id, []).append(j.rating)
        return {cid: mean(rs) for cid, rs in by.items()}

    @property
    def raters(self) -> set[str]:
        return {j.rater_id for j in self.judgments}

    @property
    def member_ids(self) -> set[str]:
        return {m.user_id for m in self.team}


def scenario_from_dict(d: dict[str, Any], registry: SkillRegistry | None = None) -> Scenario:
    registry = registry or default_registry()
    if d.get("provenance") not in ("synthetic", "real"):
        raise ValueError(f"scenario {d.get('scenario_id')}: provenance must be 'synthetic' or 'real'")
    jp = d.get("judgment_provenance", "none")
    if jp not in ("none", "simulated", "human"):
        raise ValueError("judgment_provenance must be none, simulated or human")
    judgments = [Judgment(str(j["rater_id"]), str(j["candidate_id"]), int(j["rating"])) for j in d.get("judgments", [])]
    if judgments and jp == "none":
        raise ValueError(f"scenario {d['scenario_id']}: judgments present but judgment_provenance is 'none'")
    s = Scenario(
        scenario_id=str(d["scenario_id"]),
        base_project_id=str(d.get("base_project_id") or d["scenario_id"]),
        provenance=d["provenance"],
        project=project_from_dict(d["project"], registry),
        team=tuple(profile_from_dict(p, registry) for p in d["team"]),
        candidates=tuple(profile_from_dict(p, registry) for p in d["candidates"]),
        judgments=judgments,
        judgment_provenance=jp,
        committed_elsewhere=frozenset(d.get("committed_elsewhere", [])),
        notes=d.get("notes", ""),
        raw=d,
    )
    known = {c.user_id for c in s.candidates}
    stray = {j.candidate_id for j in judgments} - known
    if stray:
        raise ValueError(f"scenario {s.scenario_id}: judgments for unknown candidates {sorted(stray)}")
    return s


def load_scenarios(paths: Iterable[Path], registry: SkillRegistry | None = None) -> list[Scenario]:
    out: list[Scenario] = []
    for path in paths:
        path = Path(path)
        files = sorted(path.glob("*.json")) if path.is_dir() else [path]
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else data.get("scenarios", [data])
            out.extend(scenario_from_dict(d, registry) for d in items)
    ids = [s.scenario_id for s in out]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate scenario ids")
    return sorted(out, key=lambda s: s.scenario_id)
