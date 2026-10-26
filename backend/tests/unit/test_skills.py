import pytest

from app.domain.models import DomainValidationError
from app.domain.skills import SkillRegistry, default_registry


@pytest.fixture
def reg():
    return default_registry()


@pytest.mark.parametrize("label", ["nodejs", "node js", "NodeJS", "Node.js", "  NODE   js ", "node"])
def test_node_aliases_map_to_one_label(reg, label):
    assert reg.normalize(label).canonical == "Node.js"


@pytest.mark.parametrize(
    "a,b",
    [("React", "React Native"), ("Python", "Django"), ("Java", "JavaScript"), ("C", "C++"), ("C++", "C#")],
)
def test_distinct_technologies_stay_separate(reg, a, b):
    assert reg.normalize(a).canonical != reg.normalize(b).canonical


def test_case_and_whitespace_variants(reg):
    assert reg.normalize("  postgreSQL ").canonical == "PostgreSQL"
    assert reg.normalize("React-Native").canonical == "React Native"


def test_unrecognised_label_is_preserved(reg):
    n = reg.normalize("  Quantum   Basket Weaving ")
    assert n.recognized is False
    assert n.rule == "unrecognized"
    assert n.canonical == "Quantum Basket Weaving"


def test_duplicates_keep_highest_proficiency(reg):
    skills, decisions, merges = reg.normalize_proficiencies(
        [("nodejs", 2), ("Node.js", 4), ("NodeJS", 1), ("React", 3)]
    )
    assert skills == {"Node.js": 4, "React": 3}
    assert len(decisions) == 4
    assert merges[0].canonical == "Node.js" and merges[0].kept_proficiency == 4


def test_unrecognised_duplicates_merge_case_insensitively(reg):
    skills, _, _ = reg.normalize_proficiencies([("Elm", 2), ("elm", 3)])
    assert skills == {"Elm": 3}


def test_invalid_proficiency_rejected(reg):
    with pytest.raises(DomainValidationError):
        reg.normalize_proficiencies([("React", 5)])
    with pytest.raises(DomainValidationError):
        reg.normalize_proficiencies([("React", 0)])


def test_empty_label_rejected(reg):
    with pytest.raises(DomainValidationError):
        reg.normalize("   ")


def test_ambiguous_alias_table_rejected():
    with pytest.raises(DomainValidationError):
        SkillRegistry({"React": ["rn"], "React Native": ["rn"]})


def test_compact_collision_rejected():
    with pytest.raises(DomainValidationError):
        SkillRegistry({"Foo.Bar": [], "foo-bar": []})


def test_shipped_table_loads(reg):
    assert "Node.js" in reg.canonical_labels
    assert len(reg.canonical_labels) > 50
