import random

import pytest

from app.domain.engine import rank_candidates
from app.domain.models import DomainValidationError
from app.domain.scoring import INITIAL_WEIGHTS, NoActiveFeatures, ranking_key, renormalize, validate_weights
from tests.factories import person, req, request, scenario_a_project, scenario_a_team


def test_initial_weights_match_paper():
    assert dict(INITIAL_WEIGHTS) == {"sem": 0.30, "gap": 0.35, "role": 0.15, "avail": 0.10, "work": 0.10}
    validate_weights(INITIAL_WEIGHTS)


@pytest.mark.parametrize(
    "weights", [{"sem": -0.1, "gap": 1.1}, {"sem": 0.5}, {"foo": 1.0}, {}, {"sem": float("nan"), "gap": 1}]
)
def test_invalid_weights_rejected(weights):
    with pytest.raises(DomainValidationError):
        validate_weights(weights)


def test_renormalize_proportionally():
    w = renormalize(INITIAL_WEIGHTS, {"sem", "role", "avail", "work"})
    assert w["sem"] == pytest.approx(0.30 / 0.65)
    assert sum(w.values()) == pytest.approx(1.0)
    with pytest.raises(NoActiveFeatures):
        renormalize({"gap": 1.0}, {"sem"})


def test_ranking_key_tie_breaks():
    keys = [
        ranking_key(0.5, 0.2, 0.9, "b"),
        ranking_key(0.5, 0.4, 0.1, "z"),
        ranking_key(0.5, 0.2, 0.9, "a"),
        ranking_key(0.6, 0.0, 0.0, "y"),
    ]
    order = [k[3] for k in sorted(keys)]
    assert order == ["y", "z", "a", "b"]


def test_scenario_a_gap_filler_outranks_more_similar_duplicate():
    """Paper Scenario A: Y (Node.js + PostgreSQL) beats X (React) despite lower f_sem."""
    project = scenario_a_project()
    x = person("x", {"React": 4, "CSS": 4}, primary_roles=["Frontend"])
    y = person("y", {"Node.js": 3, "PostgreSQL": 2}, primary_roles=["Backend"])
    result = rank_candidates(request(project, scenario_a_team(), [x, y], {"x": 0.9, "y": 0.6}))
    # Active features: sem, gap, role (async, no hours/mode) -> weights /0.80
    assert result.omitted_features == {"avail": "team_not_synchronous", "work": "team_states_no_commitment_or_mode"}
    assert result.active_weights == pytest.approx({"sem": 0.375, "gap": 0.4375, "role": 0.1875})
    by_id = {r.candidate_id: r for r in result.ranked}
    assert by_id["x"].score == pytest.approx(0.375 * 0.9)
    assert by_id["y"].score == pytest.approx(0.375 * 0.6 + 0.4375 * 1.0 + 0.1875 * 1.0)
    assert [r.candidate_id for r in result.ranked] == ["y", "x"]
    assert result.weights_renormalized


def test_team_unaware_semantic_only_would_prefer_x():
    project = scenario_a_project()
    x = person("x", {"React": 4})
    y = person("y", {"Node.js": 3, "PostgreSQL": 2})
    result = rank_candidates(request(project, scenario_a_team(), [x, y], {"x": 0.9, "y": 0.6}), {"sem": 1.0})
    assert [r.candidate_id for r in result.ranked] == ["x", "y"]


def test_scenario_c_need_beats_experience():
    reqs = (req("React", 2, 3), req("Node.js", 2, 3), req("Figma", 2, 3))
    project = scenario_a_project(requirements=reqs, vacant_roles=("Designer",))
    team = [person("d1", {"React": 4, "Node.js": 4}), person("d2", {"React": 3, "Node.js": 3})]
    p = person("p", {"React": 4, "Node.js": 4, "Docker": 4}, primary_roles=["Full-stack"])
    q = person("q", {"Figma": 2}, year=2, primary_roles=["Designer"])
    result = rank_candidates(request(project, team, [p, q], {"p": 0.8, "q": 0.5}))
    by_id = {r.candidate_id: r for r in result.ranked}
    assert by_id["p"].gain == 0.0
    assert by_id["q"].gain == pytest.approx(2 * (2 / 3) / 6)
    assert result.ranked[0].candidate_id == "q"
    adds = by_id["q"].explanation["adds"]
    assert adds[0]["skill"] == "Figma" and adds[0]["fully_covers"] is False
    assert "below the desired 3" in by_id["q"].explanation_text


def test_complete_coverage_drops_gap_and_renormalizes():
    project = scenario_a_project()
    team = [*scenario_a_team(), person("c", {"Node.js": 3, "PostgreSQL": 3})]
    result = rank_candidates(request(project, team, [person("d", {"React": 4})]))
    assert result.team_coverage.complete
    assert "gap" in result.omitted_features
    assert "gap" not in result.active_weights
    assert sum(result.active_weights.values()) == pytest.approx(1.0)
    r = result.ranked[0]
    assert r.features["gap"].value is None
    assert r.explanation["all_requirements_covered_before"]
    assert r.explanation_text.startswith("All listed requirements are already met")


def test_ineligible_never_ranked_and_reasons_kept():
    project = scenario_a_project(allowed_years=frozenset({2}))
    result = rank_candidates(
        request(project, scenario_a_team(), [person("ok", year=2), person("no", year=4), person("hid", year=2, visible=False)])
    )
    assert [r.candidate_id for r in result.ranked] == ["ok"]
    assert {d.candidate_id for d in result.excluded} == {"no", "hid"}


def test_team_full_stops_recommendations():
    project = scenario_a_project(target_size=2)
    result = rank_candidates(request(project, scenario_a_team(), [person("x")]))
    assert result.status == "team_full" and result.ranked == []


def test_scores_in_unit_interval_and_deterministic_under_reordering():
    project = scenario_a_project(synchronous=True, min_shared_slots=2, weekly_hours=10, work_mode="hybrid",
                                 vacant_roles=("Backend", "Designer"))
    team = [person("t1", {"React": 3}, availability={"a", "b", "c"}), person("t2", {"Machine Learning": 2}, availability={"a", "b"})]
    rng = random.Random(7)
    skills = ["React", "Node.js", "PostgreSQL", "Machine Learning", "Figma"]
    cands = []
    for i in range(30):
        s = {k: rng.randint(1, 4) for k in rng.sample(skills, rng.randint(0, 3))}
        cands.append(person(f"c{i:02d}", s, primary_roles=[rng.choice(["Backend", "Designer", "ML"])],
                            availability=rng.choice([None, set(), {"a"}, {"a", "b"}]),
                            weekly_hours=rng.choice([None, 5, 10, 30]), work_mode=rng.choice([None, "online", "offline"])))
    sem = {c.user_id: rng.random() for c in cands}
    r1 = rank_candidates(request(project, team, cands, sem))
    shuffled = cands[:]
    rng.shuffle(shuffled)
    r2 = rank_candidates(request(project, team, shuffled, sem))
    assert [r.candidate_id for r in r1.ranked] == [r.candidate_id for r in r2.ranked]
    assert [r.explanation_text for r in r1.ranked] == [r.explanation_text for r in r2.ranked]
    for r in r1.ranked:
        assert 0.0 <= r.score <= 1.0
        for v in r.feature_values().values():
            assert v is None or 0.0 <= v <= 1.0


def test_identical_candidates_tie_break_by_id():
    project = scenario_a_project()
    cands = [person(cid, {"Node.js": 2}) for cid in ["m", "a", "k"]]
    result = rank_candidates(request(project, scenario_a_team(), cands))
    assert [r.candidate_id for r in result.ranked] == ["a", "k", "m"]


def test_explanation_reflects_inputs():
    project = scenario_a_project(synchronous=True, min_shared_slots=3)
    team = [person("t1", {"React": 3, "Machine Learning": 3}, availability={"a", "b", "c", "d", "e", "f"})]
    y = person("y", {"PostgreSQL": 3, "React": 3}, primary_roles=["Backend"], availability={"a", "b", "c", "z"})
    r = rank_candidates(request(project, team, [y])).ranked[0]
    e = r.explanation
    assert [a["skill"] for a in e["adds"]] == ["PostgreSQL"]
    assert [d["skill"] for d in e["duplicates"]] == ["React"]
    assert [g["skill"] for g in e["remaining_gaps"]] == ["Node.js"]
    assert e["availability"]["overlap"] == 3 and e["availability"]["team_slots"] == 6
    assert sum(c["contribution"] for c in e["contributions"].values()) == pytest.approx(r.score)
    text = r.explanation_text
    assert "Adds PostgreSQL (essential; stated proficiency 3 of 4)" in text
    assert "Prefers the vacant Backend role." in text
    assert "Shares 3 of the team's 6 weekly slots." in text
    assert "Node.js remains uncovered." in text
    assert text.endswith("Proficiency is self-reported.")


def test_missing_semantic_score_is_an_error():
    with pytest.raises(ValueError):
        rank_candidates(request(scenario_a_project(), scenario_a_team(), [person("x")], {"other": 0.1}))
