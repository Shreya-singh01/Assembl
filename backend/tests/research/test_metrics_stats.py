import math

import pytest

from app.research.metrics import dcg, ndcg_at_k, precision_at_k
from app.research.stats import kendall_tau, krippendorff_alpha_ordinal, paired_wilcoxon


def test_ndcg_hand_calculated():
    labels = {"a": 3, "b": 2, "c": 0, "d": 1}
    # ranking b, a, c: DCG = 2/1 + 3/log2(3) + 0
    got = ndcg_at_k(["b", "a", "c"], labels, k=3)
    ideal = 3 + 2 / math.log2(3) + 1 / 2
    assert got == pytest.approx((2 + 3 / math.log2(3)) / ideal)
    assert ndcg_at_k(["a", "b", "d", "c"], labels, k=5) == pytest.approx(1.0)


def test_ndcg_zero_ideal_is_undefined_not_zero():
    assert ndcg_at_k(["a"], {"a": 0, "b": 0}) is None
    assert ndcg_at_k(["a"], {}) is None


def test_unjudged_candidates_are_skipped_not_scored_zero():
    labels = {"a": 3, "b": 2}
    # x and y are unjudged: condensed list is [a, b] -> perfect
    assert ndcg_at_k(["x", "a", "y", "b"], labels) == pytest.approx(1.0)
    assert precision_at_k(["x", "a", "y", "b"], labels) == 1.0


def test_precision_threshold_and_short_lists():
    labels = {"a": 2.0, "b": 1.67, "c": 3}
    assert precision_at_k(["a", "b", "c"], labels) == pytest.approx(2 / 3)  # denominator 3, not 5
    assert precision_at_k([], labels) is None


def test_dcg_empty():
    assert dcg([]) == 0


def test_alpha_hand_calculated_binary():
    ratings = [("u1", "r1", 0), ("u1", "r2", 0), ("u2", "r1", 1), ("u2", "r2", 1), ("u3", "r1", 0), ("u3", "r2", 1)]
    # Coincidences: o00=2, o11=2, o01=o10=1; n0=n1=3; alpha = 1 - 5*18 / (2*3*3*9) = 4/9
    assert krippendorff_alpha_ordinal(ratings)["alpha"] == pytest.approx(4 / 9)


def test_alpha_perfect_agreement_and_undefined_cases():
    perfect = [(u, r, v) for u, v in [("a", 0), ("b", 2), ("c", 3)] for r in ("r1", "r2", "r3")]
    assert krippendorff_alpha_ordinal(perfect)["alpha"] == pytest.approx(1.0)
    assert krippendorff_alpha_ordinal([("a", "r1", 2), ("a", "r2", 2)])["alpha"] is None
    single = krippendorff_alpha_ordinal([("a", "r1", 2), ("b", "r1", 1)])
    assert single["alpha"] is None and single["pairable_units"] == 0


def test_alpha_ordinal_penalises_distant_disagreement_more():
    near = [("u1", "r1", 2), ("u1", "r2", 3), ("u2", "r1", 0), ("u2", "r2", 0), ("u3", "r1", 3), ("u3", "r2", 3)]
    far = [("u1", "r1", 0), ("u1", "r2", 3), ("u2", "r1", 0), ("u2", "r2", 0), ("u3", "r1", 3), ("u3", "r2", 3)]
    assert krippendorff_alpha_ordinal(near)["alpha"] > krippendorff_alpha_ordinal(far)["alpha"]


def test_wilcoxon_reports_effect_and_handles_ties():
    res = paired_wilcoxon([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], [0.3, 0.5, 0.4, 0.7, 0.6, 0.9])
    assert res["n"] == 6 and res["rank_biserial"] == 1.0 and 0 < res["p_value"] < 0.1
    assert "power" in res["note"]
    zero = paired_wilcoxon([0.5, 0.5], [0.5, 0.5])
    assert zero["p_value"] is None and "zero" in zero["note"]


def test_kendall_tau():
    assert kendall_tau(["a", "b", "c"], ["a", "b", "c"]) == pytest.approx(1.0)
    assert kendall_tau(["a", "b", "c"], ["c", "b", "a"]) == pytest.approx(-1.0)
    assert kendall_tau(["a"], ["a"]) is None
