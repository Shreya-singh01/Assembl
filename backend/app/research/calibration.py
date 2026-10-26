"""Coarse grid search over the weight simplex (paper Section 4.5).

Only development scenarios may be passed in. The grid enumerates every
weight vector with entries in {0, step, 2*step, ..., 1} summing to one,
in a fixed lexicographic order; the first vector with the highest mean
development NDCG@5 wins (deterministic tie-breaking).
"""

from __future__ import annotations

from itertools import combinations
from statistics import mean
from typing import Iterator, Mapping, Sequence

from .methods import FeatureTable
from .metrics import ndcg_at_k


def simplex_grid(features: Sequence[str], step: float = 0.1) -> Iterator[dict[str, float]]:
    n_steps = round(1 / step)
    if abs(n_steps * step - 1) > 1e-9:
        raise ValueError("step must divide 1 evenly")
    k = len(features)
    if k == 1:
        yield {features[0]: 1.0}
        return
    # stars and bars: choose k-1 bar positions among n_steps + k - 1 slots
    for bars in combinations(range(n_steps + k - 1), k - 1):
        prev = -1
        parts = []
        for b in bars:
            parts.append(b - prev - 1)
            prev = b
        parts.append(n_steps + k - 1 - prev - 1)
        yield {f: p / n_steps for f, p in zip(features, parts)}


def calibrate(
    dev_tables: Mapping[str, FeatureTable],
    dev_labels: Mapping[str, Mapping[str, float]],
    features: Sequence[str],
    step: float = 0.1,
    k: int = 5,
) -> dict:
    usable = [sid for sid in dev_tables if dev_labels.get(sid)]
    if not usable:
        return {"weights": None, "dev_ndcg": None, "evaluated": 0, "dev_scenarios_used": 0,
                "note": "no judged development scenarios; calibration not possible"}
    best_w, best_score, evaluated = None, -1.0, 0
    for w in simplex_grid(features, step):
        # A vector whose positive weights all fall on features undefined for some
        # scenario cannot rank it; skip the vector rather than average over fewer scenarios.
        if any(dev_tables[sid].ids and not any(w.get(f, 0) > 0 for f in dev_tables[sid].available) for sid in usable):
            continue
        scores = []
        for sid in usable:
            table = dev_tables[sid]
            if not table.ids:
                continue
            v = ndcg_at_k(table.rank(w)[0], dev_labels[sid], k)
            if v is not None:
                scores.append(v)
        evaluated += 1
        if scores and mean(scores) > best_score + 1e-12:
            best_w, best_score = w, mean(scores)
    return {"weights": best_w, "dev_ndcg": best_score if best_w else None, "evaluated": evaluated,
            "dev_scenarios_used": len(usable), "step": step, "note": None}
