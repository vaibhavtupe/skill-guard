from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from skill_guard.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def _run_git(args: list[str], cwd: Path) -> None:
    env = {"TMPDIR": str(cwd)}
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True)


def _init_repo_with_skills(tmp_path: Path, skill_names: list[str]) -> Path:
    repo_root = tmp_path / "repo"
    skills_root = repo_root / "skills"
    skills_root.mkdir(parents=True)

    for skill_name in skill_names:
        shutil.copytree(FIXTURES / skill_name, skills_root / skill_name)

    _run_git(["init"], repo_root)
    _run_git(["config", "user.name", "Test User"], repo_root)
    _run_git(["config", "user.email", "test@example.com"], repo_root)
    _run_git(["add", "."], repo_root)
    _run_git(["commit", "-m", "initial"], repo_root)
    return repo_root


def test_check_changed_reports_multi_skill_pr(tmp_path: Path, monkeypatch) -> None:
    repo_root = _init_repo_with_skills(tmp_path, ["valid-skill", "anthropic-compliant"])
    monkeypatch.chdir(repo_root)

    valid_skill = repo_root / "skills" / "valid-skill" / "SKILL.md"
    anthropic_skill = repo_root / "skills" / "anthropic-compliant" / "SKILL.md"
    valid_skill.write_text(
        valid_skill.read_text(encoding="utf-8") + "\nExtra note.\n", encoding="utf-8"
    )
    anthropic_skill.write_text(
        anthropic_skill.read_text(encoding="utf-8") + "\nExtra policy detail.\n",
        encoding="utf-8",
    )
    _run_git(["add", "."], repo_root)
    _run_git(["commit", "-m", "modify skills"], repo_root)

    result = runner.invoke(
        app,
        [
            "check",
            str(repo_root / "skills"),
            "--changed",
            "--base-ref",
            "HEAD~1",
            "--head-ref",
            "HEAD",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    report = payload["result"]
    assert report["checked_skills"] == 2
    assert report["failed"] == 0
    assert report["status"] in ("passed", "warning")
    assert {skill["skill_name"] for skill in report["skills"]} == {
        "valid-skill",
        "anthropic-compliant",
    }


def test_check_changed_handles_no_changes_cleanly(tmp_path: Path, monkeypatch) -> None:
    repo_root = _init_repo_with_skills(tmp_path, ["valid-skill"])
    monkeypatch.chdir(repo_root)

    result = runner.invoke(
        app,
        [
            "check",
            str(repo_root / "skills"),
            "--changed",
            "--base-ref",
            "HEAD",
            "--head-ref",
            "HEAD",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["result"]["summary"] == "No changed skills detected."
    assert payload["result"]["skills"] == []


def test_check_changed_handles_rename_and_delete(tmp_path: Path, monkeypatch) -> None:
    repo_root = _init_repo_with_skills(tmp_path, ["valid-skill", "anthropic-compliant"])
    monkeypatch.chdir(repo_root)

    _run_git(["mv", "skills/valid-skill", "skills/valid-skill-renamed"], repo_root)
    renamed_skill_md = repo_root / "skills" / "valid-skill-renamed" / "SKILL.md"
    renamed_skill_md.write_text(
        renamed_skill_md.read_text(encoding="utf-8").replace(
            "name: valid-skill",
            "name: valid-skill-renamed",
            1,
        ),
        encoding="utf-8",
    )
    shutil.rmtree(repo_root / "skills" / "anthropic-compliant")
    _run_git(["add", "-A"], repo_root)
    _run_git(["commit", "-m", "rename and delete"], repo_root)

    result = runner.invoke(
        app,
        [
            "check",
            str(repo_root / "skills"),
            "--changed",
            "--base-ref",
            "HEAD~1",
            "--head-ref",
            "HEAD",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    report = payload["result"]
    assert report["checked_skills"] == 1
    assert report["skipped_skills"] == 1

    renamed = next(skill for skill in report["skills"] if skill["target_status"] == "renamed")
    deleted = next(skill for skill in report["skills"] if skill["target_status"] == "deleted")
    assert renamed["skill_name"] == "valid-skill-renamed"
    assert renamed["previous_skill_path"].endswith("/skills/valid-skill")
    assert deleted["skill_name"] == "anthropic-compliant"
