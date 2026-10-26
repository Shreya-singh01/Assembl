from app.domain.eligibility import Reason, check_eligibility
from app.domain.features import team_slots
from tests.factories import person, req, scenario_a_project, scenario_a_team


def _check(project, cand, team=None, committed=frozenset()):
    team = team or scenario_a_team()
    return check_eligibility(project, team, cand, team_slots(project, team), committed)


def codes(decision):
    return {r.code for r in decision.failures}


def test_hidden_member_and_committed_are_excluded():
    p = scenario_a_project()
    assert Reason.PROFILE_HIDDEN in codes(_check(p, person("x", visible=False)))
    assert Reason.ALREADY_MEMBER in codes(_check(p, person("alice")))
    assert Reason.COMMITTED_TO_EVENT_TEAM in codes(_check(p, person("x"), committed=frozenset({"x"})))


def test_year_rule_distinguishes_unknown_from_failure():
    p = scenario_a_project(allowed_years=frozenset({2, 3}))
    assert _check(p, person("x", year=3)).eligible
    assert codes(_check(p, person("x", year=1))) == {Reason.YEAR_NOT_ALLOWED}
    d = _check(p, person("x"))
    assert not d.eligible and codes(d) == {Reason.YEAR_UNVERIFIED}


def test_include_policy_keeps_unverified_candidates_flagged():
    p = scenario_a_project(allowed_years=frozenset({2}), unverifiable_policy="include")
    d = _check(p, person("x"))
    assert d.eligible and [u.code for u in d.unverified] == [Reason.YEAR_UNVERIFIED]
    assert not _check(p, person("y", year=4)).eligible


def test_mandatory_skill_rule():
    reqs = (req("React", 2, 3), req("Node.js", 3, 2, mandatory=True))
    p = scenario_a_project(requirements=reqs)
    assert _check(p, person("x", {"Node.js": 2})).eligible
    assert codes(_check(p, person("x", {"Node.js": 1}))) == {Reason.MANDATORY_SKILL_NOT_MET}
    assert codes(_check(p, person("x", {}, declared_absent=["Node.js"]))) == {Reason.MANDATORY_SKILL_NOT_MET}
    assert codes(_check(p, person("x", {}))) == {Reason.MANDATORY_SKILL_UNVERIFIED}


def test_importance_three_is_not_a_filter():
    # "Essential" importance (a_s = 3) affects ranking only (paper Scenario A).
    p = scenario_a_project()
    assert _check(p, person("x", {"React": 4})).eligible


def test_mandatory_role():
    p = scenario_a_project(vacant_roles=("Designer",), role_mandatory=True)
    assert _check(p, person("x", secondary_roles=["designer"])).eligible
    assert codes(_check(p, person("x", primary_roles=["Backend"]))) == {Reason.ROLE_NOT_MATCHED}
    assert codes(_check(p, person("x"))) == {Reason.ROLE_UNVERIFIED}


def test_mandatory_availability():
    p = scenario_a_project(synchronous=True, min_shared_slots=2, availability_mandatory=True)
    team = [person("m1", availability={"a", "b", "c"}), person("m2", availability={"a", "b"})]
    assert _check(p, person("x", availability={"a", "b"}), team).eligible
    assert codes(_check(p, person("x", availability={"a", "z"}), team)) == {Reason.AVAILABILITY_NOT_MET}
    assert codes(_check(p, person("x"), team)) == {Reason.AVAILABILITY_UNVERIFIED}


def test_soft_availability_never_excludes():
    p = scenario_a_project(synchronous=True, min_shared_slots=2)
    team = [person("m1", availability={"a", "b"})]
    assert _check(p, person("x", availability=set()), team).eligible
