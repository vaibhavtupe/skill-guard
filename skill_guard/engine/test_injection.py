"""Test injection helpers for skill-guard test runs."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from skill_guard.config import TestConfig
from skill_guard.models import HookError, ParsedSkill


@dataclass
class TestInjectionContext:
    skill: ParsedSkill
    config: TestConfig
    _cleanup: callable | None = None

    def run_pre(self) -> None:
        method = self.config.injection.method
        if method == "custom_hook":
            self._cleanup = _build_hook_cleanup(self.skill, self._endpoint, self.config)
            if self.config.injection.pre_test_hook:
                _run_hook(
                    Path(self.config.injection.pre_test_hook), self.skill.path, self._endpoint
                )
            return
        if method == "directory_copy":
            self._cleanup = _directory_copy_injection(self.skill, self.config)
            return
        if method == "git_push":
            self._cleanup = _git_push_injection(self.skill, self.config)
            return
        raise HookError(f"Unsupported injection method: {method}")

    def run_post(self) -> None:
        if self._cleanup:
            self._cleanup()

    @property
    def _endpoint(self) -> str:
        if not self.config.endpoint:
            raise HookError("Agent endpoint is required. Set test.endpoint or pass --endpoint.")
        return self.config.endpoint.rstrip("/")


def _build_hook_cleanup(skill: ParsedSkill, endpoint: str, config: TestConfig) -> callable | None:
    if not config.injection.post_test_hook:
        return None

    def _cleanup() -> None:
        _run_hook(Path(config.injection.post_test_hook), skill.path, endpoint)

    return _cleanup


def _directory_copy_injection(skill: ParsedSkill, config: TestConfig) -> callable:
    target_dir = config.injection.directory_copy_dir
    if not target_dir:
        raise HookError("directory_copy requires injection.directory_copy_dir")

    target_root = Path(target_dir).expanduser()
    target_root.mkdir(parents=True, exist_ok=True)

    destination = target_root / skill.path.name
    backup_path: Path | None = None

    if destination.exists():
        backup_path = target_root / f".{destination.name}.skill-guard-backup-{uuid.uuid4().hex}"
        shutil.move(destination, backup_path)

    try:
        shutil.copytree(skill.path, destination)
    except Exception as exc:  # noqa: BLE001
        if backup_path and backup_path.exists():
            shutil.move(backup_path, destination)
        raise HookError(f"directory_copy failed: {exc}") from exc

    def _cleanup() -> None:
        try:
            if destination.exists():
                shutil.rmtree(destination)
            if backup_path and backup_path.exists():
                shutil.move(backup_path, destination)
        except Exception as exc:  # noqa: BLE001
            raise HookError(f"directory_copy cleanup failed: {exc}") from exc

    return _cleanup


def _git_push_injection(skill: ParsedSkill, config: TestConfig) -> callable:
    injection = config.injection
    if not injection.git_repo_path:
        raise HookError("git_push requires injection.git_repo_path")

    repo_path = Path(injection.git_repo_path).expanduser()
    if not (repo_path / ".git").exists():
        raise HookError(f"git_repo_path is not a git repository: {repo_path}")

    skills_dir = injection.git_skills_dir or "skills"
    target_root = repo_path / skills_dir
    target_root.mkdir(parents=True, exist_ok=True)

    destination = target_root / skill.path.name
    backup_path: Path | None = None

    original_head = _git_current_head(repo_path)
    original_branch = _git_current_branch(repo_path)

    if destination.exists():
        backup_path = target_root / f".{destination.name}.skill-guard-backup-{uuid.uuid4().hex}"
        shutil.move(destination, backup_path)

    try:
        shutil.copytree(skill.path, destination)
        _git_command(["add", str(destination.relative_to(repo_path))], repo_path)

        if not _git_status_clean(repo_path):
            commit_message = (
                injection.git_commit_message or f"skill-guard test injection: {skill.metadata.name}"
            )
            _git_command(
                [
                    "-c",
                    "user.email=skill-guard@local",
                    "-c",
                    "user.name=skill-guard",
                    "commit",
                    "-m",
                    commit_message,
                ],
                repo_path,
            )
            branch = injection.git_branch or original_branch
            _git_command(["push", injection.git_remote, f"HEAD:{branch}"], repo_path)
    except HookError:
        _git_rollback(repo_path, original_head, backup_path, destination)
        raise
    except Exception as exc:  # noqa: BLE001
        _git_rollback(repo_path, original_head, backup_path, destination)
        raise HookError(f"git_push failed: {exc}") from exc

    def _cleanup() -> None:
        _git_rollback(repo_path, original_head, backup_path, destination)

    return _cleanup


def _git_current_head(repo_path: Path) -> str:
    result = _git_command(["rev-parse", "HEAD"], repo_path)
    return result.stdout.strip()


def _git_current_branch(repo_path: Path) -> str:
    result = _git_command(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    return result.stdout.strip()


def _git_status_clean(repo_path: Path) -> bool:
    result = _git_command(["status", "--porcelain"], repo_path)
    return result.stdout.strip() == ""


def _git_rollback(
    repo_path: Path, original_head: str, backup_path: Path | None, destination: Path
) -> None:
    _git_command(["reset", "--hard", original_head], repo_path, allow_failure=True)
    _git_command(["clean", "-fd"], repo_path, allow_failure=True)
    if destination.exists():
        shutil.rmtree(destination)
    if backup_path and backup_path.exists():
        shutil.move(backup_path, destination)


def _git_command(
    args: list[str],
    repo_path: Path,
    *,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0 and not allow_failure:
        stderr = _redact_credentials(proc.stderr.strip())
        stdout = _redact_credentials(proc.stdout.strip())
        details = stderr or stdout or "No output."
        raise HookError(f"git command failed ({' '.join(args)}): {details}")
    return proc


def _run_hook(hook_script: Path, skill_path: Path, endpoint: str) -> None:
    from skill_guard.engine.agent_runner import run_hook

    run_hook(hook_script, skill_path, endpoint)


def _redact_credentials(text: str) -> str:
    if not text:
        return text
    return re.sub(r"(https?://)([^@/]+)@", r"\1***@", text)
