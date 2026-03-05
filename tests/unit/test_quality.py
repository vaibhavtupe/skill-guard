from pathlib import Path

from skill_guard.config import ValidateConfig
from skill_guard.engine.quality import run_validation
from skill_guard.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_quality_valid_skill():
    skill = parse_skill(FIXTURES / "valid-skill")
    result = run_validation(skill, ValidateConfig())
    assert result.passed is True
    assert result.score >= 80
    assert result.grade in ("A", "B")


def test_quality_broken_refs():
    skill = parse_skill(FIXTURES / "broken-refs-skill")
    result = run_validation(skill, ValidateConfig())
    assert result.passed is False
    assert result.blockers >= 1
