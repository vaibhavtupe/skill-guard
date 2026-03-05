from pathlib import Path

from skill_gate.config import ConflictConfig
from skill_gate.engine.similarity import compute_similarity
from skill_gate.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_conflict_high_overlap():
    new_skill = parse_skill(FIXTURES / "conflicting-skill")
    result = compute_similarity(new_skill, FIXTURES, ConflictConfig())
    assert result.high_conflicts >= 1 or result.medium_conflicts >= 1


def test_conflict_self_excluded():
    new_skill = parse_skill(FIXTURES / "valid-skill")
    result = compute_similarity(new_skill, FIXTURES, ConflictConfig())
    # Should not conflict with itself
    assert all(m.existing_skill_name != "valid-skill" for m in result.matches)
