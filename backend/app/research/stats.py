"""Inter-rater reliability, paired significance tests and rank correlation.

Krippendorff's alpha (ordinal metric) follows Krippendorff (2011), "Computing
Krippendorff's Alpha-Reliability": coincidence matrix over pairable values,
ordinal distance d(c,k) = (sum_{g=c..k} n_g - (n_c + n_k)/2)^2.
Units rated by fewer than two raters are not pairable and are ignored.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence

from scipy import stats as sps


def krippendorff_alpha_ordinal(ratings: Iterable[tuple[str, str, int]]) -> dict:
    """ratings: (unit_id, rater_id, value). Returns alpha (None if undefined)
    plus the counts needed to judge how much to trust it."""
    by_unit: dict[str, dict[str, int]] = defaultdict(dict)
    for unit, rater, value in ratings:
        by_unit[unit][rater] = int(value)
    units = {u: list(v.values()) for u, v in by_unit.items() if len(v) >= 2}
    values = sorted({x for vals in units.values() for x in vals})
    result = {"alpha": None, "pairable_units": len(units), "pairable_values": sum(len(v) for v in units.values()),
              "units_total": len(by_unit)}
    if len(values) < 2:
        # all pairable values identical: no disagreement possible, alpha undefined
        return result
    idx = {v: i for i, v in enumerate(values)}
    n_vals = len(values)
    o = [[0.0] * n_vals for _ in range(n_vals)]
    for vals in units.values():
        m = len(vals)
        for i, a in enumerate(vals):
            for j, b in enumerate(vals):
                if i != j:
                    o[idx[a]][idx[b]] += 1.0 / (m - 1)
    n_c = [sum(row) for row in o]
    n = sum(n_c)

    def delta(c: int, k: int) -> float:
        lo, hi = min(c, k), max(c, k)
        return (sum(n_c[lo:hi + 1]) - (n_c[lo] + n_c[hi]) / 2.0) ** 2

    d_o = sum(o[c][k] * delta(c, k) for c in range(n_vals) for k in range(n_vals))
    d_e = sum(n_c[c] * n_c[k] * delta(c, k) for c in range(n_vals) for k in range(n_vals))
    if d_e == 0:
        return result
    result["alpha"] = 1.0 - (n - 1) * d_o / d_e
    return result


def paired_wilcoxon(a: Sequence[float], b: Sequence[float]) -> dict:
    """Wilcoxon signed-rank test on paired per-scenario scores (b - a), with the
    matched-pairs rank-biserial correlation as effect size."""
    if len(a) != len(b):
        raise ValueError("paired samples must have equal length")
    diffs = [y - x for x, y in zip(a, b)]
    nonzero = [d for d in diffs if abs(d) > 1e-12]
    out = {
        "n": len(diffs),
        "n_nonzero": len(nonzero),
        "mean_difference": (sum(diffs) / len(diffs)) if diffs else None,
        "median_difference": float(sorted(diffs)[len(diffs) // 2]) if diffs else None,
        "statistic": None,
        "p_value": None,
        "rank_biserial": None,
        "note": None,
    }
    if len(nonzero) == 0:
        out["note"] = "all paired differences are zero; test not applicable"
        return out
    ranks = sps.rankdata([abs(d) for d in nonzero])
    r_plus = sum(r for r, d in zip(ranks, nonzero) if d > 0)
    r_minus = sum(r for r, d in zip(ranks, nonzero) if d < 0)
    out["rank_biserial"] = (r_plus - r_minus) / (r_plus + r_minus)
    res = sps.wilcoxon(nonzero, zero_method="wilcox", alternative="two-sided")
    out["statistic"] = float(res.statistic)
    out["p_value"] = float(res.pvalue)
    if len(nonzero) < 10:
        out["note"] = f"only {len(nonzero)} non-zero pairs; the test has very little power"
    return out


def kendall_tau(order_a: Sequence[str], order_b: Sequence[str]) -> float | None:
    """Kendall's tau-b between two rankings over their common items."""
    common = [c for c in order_a if c in set(order_b)]
    if len(common) < 2:
        return None
    pos_b = {c: i for i, c in enumerate(order_b)}
    tau = sps.kendalltau(list(range(len(common))), [pos_b[c] for c in common]).statistic
    return float(tau)
