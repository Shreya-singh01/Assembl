import pytest

from app.domain.features import H_MAX, availability_fit, mode_compatibility, role_fit, team_slots, work_fit
from app.domain.models import DomainValidationError
from app.domain.semantic import cosine_clipped, profile_text, project_text
from tests.factories import person, scenario_a_project

# --- f_role -------------------------------------------------------------------


def test_role_primary_secondary_none():
    p = scenario_a_project(vacant_roles=("Backend", "Designer"))
    assert role_fit(p, person("a", primary_roles=["backend"])).value == 1.0
    assert role_fit(p, person("b", primary_roles=["ML"], secondary_roles=["Designer"])).value == 0.5
    assert role_fit(p, person("c", primary_roles=["ML"])).value == 0.0


def test_role_best_match_across_multiple_vacancies():
    p = scenario_a_project(vacant_roles=("Backend", "Designer"))
    c = person("a", primary_roles=["Designer"], secondary_roles=["Backend"])
    fv = role_fit(p, c)
    assert fv.value == 1.0 and fv.detail["role"] == "Designer"


def test_role_omitted_without_vacancies():
    assert role_fit(scenario_a_project(vacant_roles=()), person("a")).value is None


def test_role_unstated_is_zero_but_flagged():
    fv = role_fit(scenario_a_project(), person("a"))
    assert fv.value == 0.0 and fv.detail["roles_stated"] is False


# --- f_avail ------------------------------------------------------------------

SYNC = dict(synchronous=True, min_shared_slots=3)


def _team(*avails):
    return [person(f"m{i}", availability=a) for i, a in enumerate(avails)]


def test_team_slots_all_vs_majority():
    team = _team({"mon-eve", "tue-eve", "wed-eve"}, {"mon-eve", "tue-eve"}, {"mon-eve", "sat-am"})
    assert team_slots(scenario_a_project(**SYNC), team).slots == {"mon-eve"}
    maj = team_slots(scenario_a_project(**SYNC, availability_policy="majority"), team).slots
    assert maj == {"mon-eve", "tue-eve"}


def test_team_slots_ignore_members_without_availability():
    team = [*_team({"a", "b"}), person("x")]
    s = team_slots(scenario_a_project(**SYNC), team)
    assert s.slots == {"a", "b"} and s.members_with_availability == 1


def test_availability_ratio_and_cap():
    p = scenario_a_project(**SYNC)
    slots = team_slots(p, _team({"a", "b", "c", "d"}))
    assert availability_fit(p, slots, person("c", availability={"a", "b"})).value == pytest.approx(2 / 3)
    assert availability_fit(p, slots, person("c", availability={"a", "b", "c", "d"})).value == 1.0


def test_availability_unknown_is_neutral_and_flagged():
    p = scenario_a_project(**SYNC)
    fv = availability_fit(p, team_slots(p, _team({"a"})), person("c"))
    assert fv.value == 0.5 and fv.status == "neutral_unknown"


def test_availability_stated_no_overlap_is_zero():
    p = scenario_a_project(**SYNC)
    fv = availability_fit(p, team_slots(p, _team({"a"})), person("c", availability=set()))
    assert fv.value == 0.0 and fv.status == "computed"


def test_availability_omitted_for_async_team():
    p = scenario_a_project()
    assert availability_fit(p, team_slots(p, _team({"a"})), person("c", availability={"a"})).value is None


def test_synchronous_requires_positive_h():
    with pytest.raises(DomainValidationError):
        scenario_a_project(synchronous=True, min_shared_slots=0)


# --- f_work -------------------------------------------------------------------


@pytest.mark.parametrize(
    "a,b,expected",
    [("online", "online", 1), ("offline", "hybrid", 1), ("hybrid", "online", 1), ("online", "offline", 0)],
)
def test_mode_compatibility(a, b, expected):
    assert mode_compatibility(a, b) == expected


def test_work_fit_hand_calculated():
    p = scenario_a_project(weekly_hours=10, work_mode="offline")
    c = person("c", weekly_hours=20, work_mode="online")
    # commitment = 1 - 10/39; mode = 0 -> mean
    assert work_fit(p, c).value == pytest.approx((1 - 10 / H_MAX + 0) / 2)


def test_work_fit_unknown_parts_neutral():
    p = scenario_a_project(weekly_hours=10, work_mode="hybrid")
    fv = work_fit(p, person("c", weekly_hours=10))
    assert fv.value == pytest.approx((1 + 0.5) / 2)
    assert fv.detail["unknown"] == ["work_mode"]


def test_work_fit_uses_only_stated_team_components():
    p = scenario_a_project(work_mode="online")
    assert work_fit(p, person("c", weekly_hours=40, work_mode="online")).value == 1.0


def test_work_fit_omitted_when_team_states_nothing():
    assert work_fit(scenario_a_project(), person("c", weekly_hours=5)).value is None


def test_invalid_hours_and_mode_rejected():
    with pytest.raises(DomainValidationError):
        person("c", weekly_hours=100)
    with pytest.raises(DomainValidationError):
        person("c", work_mode="remote")


# --- f_sem --------------------------------------------------------------------


def test_cosine_clipped_bounds():
    assert cosine_clipped([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine_clipped([1, 0], [-1, 0]) == 0.0
    assert cosine_clipped([0, 0], [1, 0]) == 0.0
    assert cosine_clipped([1, 1], [1, 0]) == pytest.approx(2 ** -0.5)


def test_cosine_dimension_mismatch():
    with pytest.raises(ValueError):
        cosine_clipped([1, 0], [1, 0, 0])


def test_cosine_non_finite_is_zero():
    assert cosine_clipped([float("nan"), 1], [1, 1]) == 0.0


def test_profile_text_template_excludes_proficiency_numbers():
    t = profile_text(person("c", {"React": 3, "Node.js": 2}, interests=["fintech"], primary_roles=["Backend"],
                            project_summaries=["Built a REST API"]))
    assert t == "Skills: Node.js, React. Interests: fintech. Preferred roles: Backend. Projects: Built a REST API."


def test_project_text_combines_description_and_skills():
    t = project_text(scenario_a_project())
    assert t.endswith("Required skills: React, Machine Learning, Node.js, PostgreSQL.")
