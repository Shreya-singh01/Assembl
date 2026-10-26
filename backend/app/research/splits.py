"""Leakage-aware development/test split (paper Section 4.6, "Splits and leakage").

Scenarios sharing a base project or any existing team member are joined into
one group (union-find), and whole groups are assigned to a split, so a
near-duplicate of a test scenario never influences calibrated weights.
"""

from __future__ import annotations

import random
from typing import Sequence

from .scenario import Scenario


def leakage_groups(scenarios: Sequence[Scenario]) -> list[list[str]]:
    parent = {s.scenario_id: s.scenario_id for s in scenarios}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    owner: dict[str, str] = {}
    for s in scenarios:
        for key in [f"project:{s.base_project_id}", *(f"member:{m}" for m in s.member_ids)]:
            if key in owner:
                union(owner[key], s.scenario_id)
            else:
                owner[key] = s.scenario_id
    groups: dict[str, list[str]] = {}
    for s in scenarios:
        groups.setdefault(find(s.scenario_id), []).append(s.scenario_id)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: g[0])


def split_scenarios(scenarios: Sequence[Scenario], dev_fraction: float = 0.5, seed: int = 13) -> dict:
    if not 0 < dev_fraction < 1:
        raise ValueError("dev_fraction must be in (0, 1)")
    groups = leakage_groups(scenarios)
    rng = random.Random(seed)
    order = groups[:]
    rng.shuffle(order)
    target = round(dev_fraction * len(scenarios))
    dev: list[str] = []
    test: list[str] = []
    for g in order:
        (dev if len(dev) < target else test).extend(g)
    if not test and len(order) > 1:  # keep at least one group for testing
        last = order[-1]
        dev = [s for s in dev if s not in last]
        test = list(last)
    return {
        "seed": seed,
        "dev_fraction": dev_fraction,
        "dev": sorted(dev),
        "test": sorted(test),
        "groups": groups,
        "warning": None if len(groups) > 1 else "only one leakage group: no independent test split possible",
    }
