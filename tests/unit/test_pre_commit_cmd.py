from __future__ import annotations

from pathlib import Path

from skill_guard.commands.pre_commit import collect_skill_roots, pre_commit_run

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_collect_skill_roots_deduplicates_multiple_files_in_same_skill_dir(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill-a"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: skill-a\ndescription: Use when validating.\n---\n", encoding="utf-8"
    )
    ref_file = skill_dir / "references" / "note.md"
    ref_file.write_text("note", encoding="utf-8")

    roots = collect_skill_roots([skill_dir / "SKILL.md", ref_file])

    assert roots == [skill_dir.resolve()]


def test_pre_commit_run_skips_non_skill_files(tmp_path: Path, capsys) -> None:
    other_file = tmp_path / "README.md"
    other_file.write_text("docs", encoding="utf-8")

    exit_code = pre_commit_run("validate", [other_file])

    assert exit_code == 0
    assert "No skill changes detected." in capsys.readouterr().out


def test_pre_commit_run_returns_non_zero_when_one_skill_fails() -> None:
    passing_skill = FIXTURES / "valid-skill"
    failing_skill = FIXTURES / "invalid-skill"

    exit_code = pre_commit_run("validate", [passing_skill / "SKILL.md", failing_skill / "SKILL.md"])

    assert exit_code != 0
