from pathlib import Path

import pytest

from skill_gate.models import SkillParseError
from skill_gate.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_parse_valid_skill():
    skill = parse_skill(FIXTURES / "valid-skill")
    assert skill.metadata.name == "valid-skill"
    assert skill.has_scripts is True
    assert skill.has_references is True
    assert skill.has_evals is True
    assert skill.evals_config is not None
    assert len(skill.evals_config.tests) == 3


def test_parse_invalid_skill_missing_description():
    with pytest.raises(SkillParseError):
        parse_skill(FIXTURES / "invalid-skill")


def test_parse_missing_skill_md(tmp_path: Path):
    with pytest.raises(SkillParseError):
        parse_skill(tmp_path)
