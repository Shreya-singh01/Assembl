import copy
from dataclasses import replace

import pytest

from app.domain.engine import rank_candidates
from app.domain.models import RecommendationRequest
from app.domain.scoring import INITIAL_WEIGHTS
from app.research.calibration import calibrate, simplex_grid
from app.research.methods import M4_WEIGHTS, METHODS, FeatureTable, eligible_pool, run_methods
from app.research.pooling import build_pool, judging_packet
from app.research.report import render_markdown
from app.research.runner import EvalConfig, Evaluator
from app.research.scenario import scenario_from_dict
from app.research.splits import leakage_groups, split_scenarios
from app.research.synthetic import generate
from app.services.embeddings import HashingEncoder


@pytest.fixture(scope="module")
def raw():
    return generate(seed=3, per_project=5, pool_size=14, population=120)


@pytest.fixture(scope="module")
def scenarios(raw):
    return [scenario_from_dict(d) for d in raw]


@pytest.fixture(scope="module")
def ev():
    return Evaluator(HashingEncoder())


def test_synthetic_data_is_labelled(raw):
    assert len(raw) == 30
    assert all(d["provenance"] == "synthetic" and d["judgment_provenance"] == "simulated" for d in raw)
    assert {len(d["team"]) for d in raw} >= {1, 2}


def test_feature_table_reproduces_engine(scenarios, ev):
    for s in scenarios[:10]:
        pool, _ = eligible_pool(s)
        sem = ev.semantic(s, pool)
        table = FeatureTable.build(s, pool, sem)
        for weights in (INITIAL_WEIGHTS, {"sem": 0.2, "gap": 0.2, "role": 0.2, "avail": 0.2, "work": 0.2}):
            res = rank_candidates(RecommendationRequest(s.project, s.team, tuple(pool), sem), weights)
            assert table.rank(weights)[0] == [r.candidate_id for r in res.ranked]


def test_all_methods_rank_the_same_eligible_pool(scenarios, ev):
    for s in scenarios:
        pool, decisions = eligible_pool(s)
        ids = {c.user_id for c in pool}
        assert ids == {d.candidate_id for d in decisions if d.eligible}
        ranks = run_methods(s, pool, ev.semantic(s, pool))
        for m in METHODS:
            assert set(ranks[m]) == ids, m


def test_team_independent_baselines_ignore_membership(scenarios, ev):
    s = next(x for x in scenarios if len(x.team) >= 2)
    alt = replace(s, team=s.team[:1])
    pool_a, _ = eligible_pool(s)
    pool_b, _ = eligible_pool(alt)
    common = [c for c in pool_a if c.user_id in {p.user_id for p in pool_b}]
    sem = ev.semantic(s, common)
    a = run_methods(s, common, sem, table=FeatureTable.build(s, common, sem))
    b = run_methods(alt, common, sem, table=FeatureTable.build(alt, common, sem, alt.team))
    for m in ("M1", "M2", "M3"):
        assert a[m] == b[m]


def test_m4_weights_rescaled():
    assert sum(M4_WEIGHTS.values()) == pytest.approx(0.65)  # engine renormalises them to 0.4615 / 0.5385


def test_pooling_reproducible_and_anonymised(scenarios, ev):
    s = scenarios[0]
    pool, _ = eligible_pool(s)
    ranks = run_methods(s, pool, ev.semantic(s, pool))
    ids = [c.user_id for c in pool]
    p1 = build_pool(ranks, ids, top_n=3, extra=2, seed=5)
    p2 = build_pool(ranks, ids, top_n=3, extra=2, seed=5)
    assert p1 == p2
    assert set().union(*(set(r[:3]) for r in ranks.values())) <= set(p1)
    packet = judging_packet(s, p1)
    flat = str({k: v for k, v in packet.items() if k != "_label_to_candidate"})
    assert all(cid not in flat for cid in ids)
    assert "M5" not in flat and "score" not in flat


def test_split_keeps_leakage_groups_together(scenarios):
    split = split_scenarios(scenarios, 0.5, seed=1)
    assert not set(split["dev"]) & set(split["test"])
    for g in leakage_groups(scenarios):
        assert set(g) <= set(split["dev"]) or set(g) <= set(split["test"])
    assert split == split_scenarios(scenarios, 0.5, seed=1)


def test_shared_member_merges_groups(raw):
    a, b = copy.deepcopy(raw[0]), copy.deepcopy(raw[7])
    assert a["base_project_id"] != b["base_project_id"]
    b["team"][0]["user_id"] = a["team"][0]["user_id"]
    groups = leakage_groups([scenario_from_dict(a), scenario_from_dict(b)])
    assert len(groups) == 1


def test_simplex_grid():
    grid = list(simplex_grid(["a", "b", "c"], 0.5))
    assert len(grid) == 6
    assert all(sum(w.values()) == pytest.approx(1) for w in grid)


def test_calibration_without_labels_is_not_performed(scenarios, ev):
    s = scenarios[0]
    pool, _ = eligible_pool(s)
    table = FeatureTable.build(s, pool, ev.semantic(s, pool))
    out = calibrate({s.scenario_id: table}, {s.scenario_id: {}}, ["sem", "gap"], 0.5)
    assert out["weights"] is None and "not possible" in out["note"]


def test_full_run_dev_only_calibration_and_honest_reporting(scenarios, ev, monkeypatch):
    seen: list[set[str]] = []
    import app.research.runner as runner_mod

    real = runner_mod.calibrate

    def spy(dev_tables, dev_labels, *a, **kw):
        seen.append(set(dev_tables))
        return real(dev_tables, dev_labels, *a, **kw)

    monkeypatch.setattr(runner_mod, "calibrate", spy)
    run = ev.evaluate(scenarios, EvalConfig(grid_step=0.25, run_robustness=True, timing_repeats=1))
    dev, test = set(run["split"]["dev"]), set(run["split"]["test"])
    assert seen and all(keys <= dev and not keys & test for keys in seen)
    assert run["status"] == "pipeline-demonstration" and run["is_research_evidence"] is False
    assert any("SIMULATED" in w for w in run["warnings"])
    assert all(m["mandatory_violations"] == 0 for m in run["results"].values())
    assert run["robustness"]["changed_membership"]["team_independent_methods_unchanged"] is True
    assert run["robustness"]["already_covered"]["failed"] == []
    md = render_markdown(run)
    assert "NOT RESEARCH EVIDENCE" in md


def test_unjudged_dataset_reports_not_measured(raw, ev):
    unjudged = []
    for d in raw[:10]:
        d = copy.deepcopy(d)
        d["judgments"], d["judgment_provenance"] = [], "none"
        unjudged.append(scenario_from_dict(d))
    run = ev.evaluate(unjudged, EvalConfig(run_robustness=False, timing_repeats=1))
    for m in run["results"].values():
        assert m["ndcg@5"] == {"value": None, "n": 0, "status": "not measured"}
        assert m["precision@5"]["status"] == "not measured"
        assert m["added_coverage@5"]["status"] == "measured"
    assert "not measured" in render_markdown(run)
    assert run["calibration"]["M5"]["used"].startswith("initial")


def test_judgments_need_declared_provenance(raw):
    d = copy.deepcopy(raw[0])
    d["judgment_provenance"] = "none"
    with pytest.raises(ValueError):
        scenario_from_dict(d)
