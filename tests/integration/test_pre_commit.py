"""Integration tests for skill-guard-pre-commit entrypoint."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from skill_guard.commands.pre_commit import collect_skill_roots, main, pre_commit_run

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


class TestCollectSkillRoots:
    def test_resolves_skill_md_file_to_root(self, tmp_path: Path) -> None:
        skill = tmp_path / "my-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        roots = collect_skill_roots([skill / "SKILL.md"])
        assert roots == [skill]

    def test_resolves_nested_file_to_skill_root(self, tmp_path: Path) -> None:
        skill = tmp_path / "my-skill"
        (skill / "scripts").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        roots = collect_skill_roots([skill / "scripts" / "run.sh"])
        assert roots == [skill]

    def test_deduplicates_multiple_files_in_same_skill(self, tmp_path: Path) -> None:
        skill = tmp_path / "my-skill"
        (skill / "scripts").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        roots = collect_skill_roots(
            [
                skill / "SKILL.md",
                skill / "scripts" / "run.sh",
            ]
        )
        assert len(roots) == 1

    def test_ignores_paths_with_no_skill_root(self, tmp_path: Path) -> None:
        roots = collect_skill_roots([tmp_path / "not-a-skill" / "file.txt"])
        assert roots == []


class TestPreCommitRun:
    def test_validate_returns_0_on_valid_skill(self) -> None:
        exit_code = pre_commit_run("validate", [FIXTURES / "valid-skill" / "SKILL.md"])
        assert exit_code == 0

    def test_validate_returns_nonzero_on_invalid_skill(self) -> None:
        # invalid-skill has a missing description — parse error (exit 4) or blocker (exit 1)
        exit_code = pre_commit_run("validate", [FIXTURES / "invalid-skill" / "SKILL.md"])
        assert exit_code != 0

    def test_secure_returns_0_on_clean_skill(self) -> None:
        exit_code = pre_commit_run("secure", [FIXTURES / "valid-skill" / "SKILL.md"])
        assert exit_code == 0

    def test_secure_returns_1_on_malicious_skill(self) -> None:
        exit_code = pre_commit_run("secure", [FIXTURES / "malicious-skill" / "SKILL.md"])
        assert exit_code == 1

    def test_check_returns_nonzero_on_conflicting_skill(self) -> None:
        # valid-skill conflicts with other fixtures in the same dir — check returns nonzero
        exit_code = pre_commit_run("check", [FIXTURES / "valid-skill" / "SKILL.md"])
        assert exit_code != 0

    def test_unknown_command_returns_nonzero(self) -> None:
        exit_code = pre_commit_run("unknown-cmd", [FIXTURES / "valid-skill" / "SKILL.md"])
        assert exit_code != 0

    def test_no_skill_changes_returns_0(self, tmp_path: Path) -> None:
        exit_code = pre_commit_run("validate", [tmp_path / "not-a-skill.txt"])
        assert exit_code == 0

    def test_multiple_skills_all_valid(self) -> None:
        exit_code = pre_commit_run(
            "validate",
            [
                FIXTURES / "valid-skill" / "SKILL.md",
                FIXTURES / "anthropic-compliant" / "SKILL.md",
            ],
        )
        assert exit_code in (0, 2)

    def test_multiple_skills_one_invalid_returns_nonzero(self) -> None:
        exit_code = pre_commit_run(
            "validate",
            [
                FIXTURES / "valid-skill" / "SKILL.md",
                FIXTURES / "invalid-skill" / "SKILL.md",
            ],
        )
        assert exit_code != 0


class TestPreCommitEntrypoint:
    @pytest.mark.integration
    def test_entrypoint_validate_via_subprocess(self) -> None:
        entrypoint = shutil.which("skill-guard-pre-commit")
        if not entrypoint:
            pytest.skip("skill-guard-pre-commit entrypoint not installed")

        result = subprocess.run(
            [entrypoint, "validate", str(FIXTURES / "valid-skill" / "SKILL.md")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


class TestMain:
    def test_main_exits_nonzero_with_no_args(self) -> None:
        assert main([]) == 3

    def test_main_validate_valid_skill(self) -> None:
        assert main(["validate", str(FIXTURES / "valid-skill" / "SKILL.md")]) == 0

    def test_main_validate_invalid_skill_exits_nonzero(self) -> None:
        assert main(["validate", str(FIXTURES / "invalid-skill" / "SKILL.md")]) != 0

    def test_main_unknown_command_exits_nonzero(self) -> None:
        assert main(["badcmd", str(FIXTURES / "valid-skill" / "SKILL.md")]) != 0
