import pytest

from app.domain.coverage import gap_feature, marginal_gain, skill_coverage, team_coverage
from app.domain.models import DomainValidationError, Requirement
from tests.factories import SCENARIO_A_REQS, person, req, scenario_a_team


def test_skill_coverage_uses_strongest_member():
    r = req("React", 2, 3)
    team = [person("a", {"React": 1}), person("b", {"React": 2})]
    assert skill_coverage(r, team).coverage == pytest.approx(2 / 3)


def test_skill_coverage_is_capped_at_one():
    assert skill_coverage(req("ML", 1, 2), [person("a", {"ML": 4})]).coverage == 1.0


def test_hand_calculated_team_coverage():
    rep = team_coverage(SCENARIO_A_REQS, scenario_a_team())
    # (2*1 + 2*1 + 3*0 + 3*0) / 10
    assert rep.overall == pytest.approx(0.4)
    assert rep.by_skill()["Node.js"].coverage == 0.0
    assert not rep.complete


def test_frontend_duplicate_adds_nothing_backend_closes_gap():
    team = scenario_a_team()
    frontend = person("x", {"React": 4, "CSS": 4, "TypeScript": 3})
    backend = person("y", {"Node.js": 3, "PostgreSQL": 2})
    g_x, _ = marginal_gain(SCENARIO_A_REQS, team, frontend)
    g_y, after_y = marginal_gain(SCENARIO_A_REQS, team, backend)
    assert g_x == 0.0
    assert g_y == pytest.approx(0.6)
    assert after_y.complete
    assert gap_feature(g_x, 0.4) == 0.0
    assert gap_feature(g_y, 0.4) == pytest.approx(1.0)


def test_partial_contribution():
    # Node.js 2 of desired 3 -> C = 2/3; coverage = (4 + 3*2/3)/10 = 0.6; G = 0.2; f_gap = 0.2/0.6
    g, _ = marginal_gain(SCENARIO_A_REQS, scenario_a_team(), person("z", {"Node.js": 2}))
    assert g == pytest.approx(0.2)
    assert gap_feature(g, 0.4) == pytest.approx(1 / 3)


def test_unrequired_skills_do_not_count():
    g, _ = marginal_gain(SCENARIO_A_REQS, scenario_a_team(), person("u", {"Rust": 4, "Go": 4, "Figma": 4}))
    assert g == 0.0


def test_unknown_and_absent_both_zero_in_paper_formula():
    unknown = person("u", {})
    absent = person("v", {}, declared_absent=["Node.js"])
    assert unknown.skill_status("Node.js") == "unknown"
    assert absent.skill_status("Node.js") == "absent"
    assert unknown.proficiency("Node.js") == absent.proficiency("Node.js") == 0.0


def test_experimental_unknown_value_variant():
    # Experimental variant only: impute 1 for unstated skills, never for declared-absent ones.
    team = [person("a", {"React": 3}), person("b", {}, declared_absent=["Node.js"])]
    reqs = (req("React", 1, 3), req("Node.js", 1, 2))
    assert team_coverage(reqs, team, unknown_value=1.0).by_skill()["Node.js"].coverage == pytest.approx(0.5)
    assert team_coverage(reqs, team).by_skill()["Node.js"].coverage == 0.0


def test_complete_coverage_makes_gap_undefined():
    assert gap_feature(0.0, 1.0) is None
    assert gap_feature(0.0, 1.0 - 1e-12) is None


def test_empty_requirements_rejected():
    with pytest.raises(DomainValidationError):
        team_coverage((), [person("a")])


@pytest.mark.parametrize("importance", [0, 4, -1])
def test_invalid_importance_rejected(importance):
    with pytest.raises(DomainValidationError):
        Requirement("React", importance, 2)


@pytest.mark.parametrize("desired", [0, 5, -2])
def test_invalid_desired_proficiency_rejected(desired):
    with pytest.raises(DomainValidationError):
        Requirement("React", 2, desired)


@pytest.mark.parametrize("level", [0, 5, 2.5, True])
def test_invalid_profile_proficiency_rejected(level):
    with pytest.raises(DomainValidationError):
        person("a", {"React": level})


# --- metamorphic properties ---------------------------------------------------

def test_adding_member_never_decreases_coverage():
    team = list(scenario_a_team())
    before = team_coverage(SCENARIO_A_REQS, team).overall
    for extra in [person("n1", {}), person("n2", {"React": 1}), person("n3", {"Node.js": 4})]:
        team.append(extra)
        now = team_coverage(SCENARIO_A_REQS, team).overall
        assert now >= before
        before = now


def test_unrequired_skill_changes_do_not_change_gain():
    base = person("c", {"Node.js": 2})
    variant = person("c", {"Node.js": 2, "Rust": 4, "Figma": 1})
    team = scenario_a_team()
    assert marginal_gain(SCENARIO_A_REQS, team, base)[0] == marginal_gain(SCENARIO_A_REQS, team, variant)[0]


def test_membership_change_changes_gain():
    cand = person("c", {"Node.js": 3})
    team = scenario_a_team()
    g1, _ = marginal_gain(SCENARIO_A_REQS, team, cand)
    g2, _ = marginal_gain(SCENARIO_A_REQS, [*team, person("d", {"Node.js": 3})], cand)
    assert g1 > 0 and g2 == 0.0


def test_gap_feature_in_unit_interval_over_grid():
    import itertools

    team = scenario_a_team()
    base = team_coverage(SCENARIO_A_REQS, team).overall
    for n, p in itertools.product(range(0, 5), range(0, 5)):
        skills = {k: v for k, v in {"Node.js": n, "PostgreSQL": p}.items() if v}
        g, _ = marginal_gain(SCENARIO_A_REQS, team, person("c", skills))
        f = gap_feature(g, base)
        assert 0.0 <= f <= 1.0
