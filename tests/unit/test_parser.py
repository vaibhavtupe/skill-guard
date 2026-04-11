from pathlib import Path

import pytest

from skill_guard.models import SkillParseError
from skill_guard.parser import parse_skill

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


def test_parse_conflict_ignore_frontmatter():
    skill = parse_skill(FIXTURES / "ignore-conflict-skill")
    assert skill.metadata.conflict_ignore == ["conflicting-skill"]


def test_parse_missing_skill_md(tmp_path: Path):
    with pytest.raises(SkillParseError):
        parse_skill(tmp_path)


def test_parse_evals_json_only():
    skill = parse_skill(FIXTURES / "evals-json-only")
    assert skill.has_evals is True
    assert skill.evals_config is not None
    assert len(skill.evals_config.tests) == 1
    assert skill.evals_config.tests[0].prompt is not None


def test_parse_evals_json_takes_precedence_over_yaml(tmp_path: Path) -> None:
    skill_dir = tmp_path / "precedence-skill"
    evals_dir = skill_dir / "evals"
    prompts_dir = evals_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '---\nname: precedence-skill\ndescription: "Use when eval precedence must be verified."\n---\n',
        encoding="utf-8",
    )
    (prompts_dir / "yaml.md").write_text("yaml prompt", encoding="utf-8")
    (evals_dir / "config.yaml").write_text(
        "tests:\n  - name: yaml-test\n    prompt_file: prompts/yaml.md\n",
        encoding="utf-8",
    )
    (evals_dir / "evals.json").write_text(
        (
            "{\n"
            '  "skill_name": "precedence-skill",\n'
            '  "evals": [\n'
            '    {"id": 1, "prompt": "json prompt", "expected_output": "json"}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    skill = parse_skill(skill_dir)

    assert skill.evals_config is not None
    assert len(skill.evals_config.tests) == 1
    assert skill.evals_config.tests[0].prompt == "json prompt"
    assert skill.evals_config.tests[0].prompt_file is None


def test_parse_invalid_evals_json(tmp_path: Path):
    skill_dir = tmp_path / "bad-evals"
    evals_dir = skill_dir / "evals"
    evals_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '---\nname: bad-evals\ndescription: "bad evals"\n---\n',
        encoding="utf-8",
    )
    (evals_dir / "evals.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(SkillParseError):
        parse_skill(skill_dir)
