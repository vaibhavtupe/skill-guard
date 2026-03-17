from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from skill_guard.config import TestConfig
from skill_guard.engine import test_injection
from skill_guard.engine.test_injection import TestInjectionContext
from skill_guard.models import HookError
from skill_guard.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_custom_hook_runs_post_on_pre_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    skill = parse_skill(FIXTURES / "valid-skill")
    calls: list[str] = []

    def fake_run_hook(hook_script: Path, skill_path: Path, endpoint: str) -> None:
        calls.append(hook_script.name)
        if hook_script.name == "pre.sh":
            raise HookError("pre hook failed")

    monkeypatch.setattr(test_injection, "_run_hook", fake_run_hook)

    config = TestConfig(
        endpoint="https://mock-agent.test",
        model="gpt-4.1",
        injection={
            "method": "custom_hook",
            "pre_test_hook": str(skill.path / "pre.sh"),
            "post_test_hook": str(skill.path / "post.sh"),
        },
    )

    ctx = TestInjectionContext(skill=skill, config=config)
    with pytest.raises(HookError, match="pre hook failed"):
        ctx.run_pre()
    ctx.run_post()

    assert calls == ["pre.sh", "post.sh"]


def test_directory_copy_injection_handles_collision(tmp_path: Path) -> None:
    skill = parse_skill(FIXTURES / "valid-skill")
    target_root = tmp_path / "agent_skills"
    target_root.mkdir()

    existing = target_root / skill.path.name
    existing.mkdir()
    (existing / "original.txt").write_text("original", encoding="utf-8")

    config = TestConfig(
        endpoint="https://mock-agent.test",
        model="gpt-4.1",
        injection={
            "method": "directory_copy",
            "directory_copy_dir": str(target_root),
        },
    )

    ctx = TestInjectionContext(skill=skill, config=config)
    ctx.run_pre()

    injected = target_root / skill.path.name
    assert (injected / "SKILL.md").exists()

    ctx.run_post()

    restored = target_root / skill.path.name
    assert (restored / "original.txt").read_text(encoding="utf-8") == "original"


def test_git_push_rolls_back_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill = parse_skill(FIXTURES / "valid-skill")
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    (repo_path / "skills").mkdir()

    calls: list[list[str]] = []

    def fake_git_command(args: list[str], repo: Path, *, allow_failure: bool = False):
        calls.append(args)
        if args[:2] == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, stdout="abc123\n", stderr="")
        if args[:2] == ["rev-parse", "--abbrev-ref"]:
            return subprocess.CompletedProcess(args, 0, stdout="main\n", stderr="")
        if args[:2] == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(args, 0, stdout=" M skills/valid-skill/SKILL.md\n", stderr="")
        if args[0] == "push":
            if allow_failure:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="auth failed")
            raise HookError("git command failed (push): auth failed")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(test_injection, "_git_command", fake_git_command)

    config = TestConfig(
        endpoint="https://mock-agent.test",
        model="gpt-4.1",
        injection={
            "method": "git_push",
            "git_repo_path": str(repo_path),
            "git_remote": "origin",
        },
    )

    ctx = TestInjectionContext(skill=skill, config=config)

    with pytest.raises(HookError, match="git command failed"):
        ctx.run_pre()

    assert ["reset", "--hard", "abc123"] in calls
    assert ["clean", "-fd"] in calls
