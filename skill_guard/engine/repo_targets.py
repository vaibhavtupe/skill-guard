"""Helpers for resolving changed skill targets inside a repository."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChangedPath:
    """A single git diff path entry."""

    status: str
    old_path: Path | None
    new_path: Path | None


@dataclass(frozen=True)
class ChangedSkillTarget:
    """A skill root selected from repo changes."""

    root: Path
    status: str
    changed_paths: tuple[Path, ...] = ()
    previous_root: Path | None = None


@dataclass(frozen=True)
class ChangedSkillSelection:
    """Resolved changed-skill selection for a repo-aware check run."""

    repo_root: Path
    target_root: Path
    base_ref: str | None
    head_ref: str | None
    targets: tuple[ChangedSkillTarget, ...]
    deleted_roots: tuple[Path, ...]


def find_skill_root(path: Path) -> Path | None:
    """Walk up from a path until a skill root is found."""
    candidate = path.resolve()
    if candidate.is_file():
        candidate = candidate.parent

    for current in (candidate, *candidate.parents):
        if (current / "SKILL.md").is_file():
            return current
    return None


def collect_skill_roots(paths: list[Path]) -> list[Path]:
    """Resolve file paths to unique skill roots."""
    roots: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        root = find_skill_root(path)
        if root is None or root in seen:
            continue
        seen.add(root)
        roots.append(root)
    return roots


def resolve_changed_skill_selection(
    target_root: Path,
    *,
    base_ref: str | None = None,
    head_ref: str | None = None,
) -> ChangedSkillSelection:
    """Resolve changed skills under a target root from git diff output."""
    repo_root = _git_repo_root(target_root)
    resolved_target_root = target_root.resolve()
    if not resolved_target_root.exists():
        raise ValueError(f"Target path does not exist: {target_root}")
    if not resolved_target_root.is_dir():
        raise ValueError("Changed-skill detection requires a directory target.")

    resolved_base = base_ref or _default_base_ref(repo_root, head_ref or "HEAD")
    changed_paths = _git_diff_name_status(repo_root, resolved_base, head_ref or "HEAD")

    targets_by_root: dict[Path, ChangedSkillTarget] = {}
    deleted_roots: set[Path] = set()
    target_root_rel = resolved_target_root.relative_to(repo_root)

    for changed in changed_paths:
        candidate_new = _resolve_candidate_root(
            repo_root,
            target_root_rel,
            resolved_target_root,
            changed.new_path,
        )
        candidate_old = _resolve_candidate_root(
            repo_root,
            target_root_rel,
            resolved_target_root,
            changed.old_path,
        )

        if changed.status.startswith("R") and candidate_new is not None:
            previous_root = candidate_old or (
                _infer_deleted_root(repo_root, target_root_rel, changed.old_path)
                if changed.old_path is not None
                else None
            )
            if previous_root == candidate_new:
                previous_root = None
            targets_by_root[candidate_new] = ChangedSkillTarget(
                root=candidate_new,
                status="renamed",
                changed_paths=tuple(
                    path for path in (changed.old_path, changed.new_path) if path is not None
                ),
                previous_root=previous_root,
            )
            continue

        if candidate_new is not None:
            existing = targets_by_root.get(candidate_new)
            targets_by_root[candidate_new] = ChangedSkillTarget(
                root=candidate_new,
                status="modified",
                changed_paths=_merge_paths(existing, changed.old_path, changed.new_path),
                previous_root=existing.previous_root if existing is not None else None,
            )
            continue

        if changed.status.startswith("D") and changed.old_path is not None:
            deleted_root = _infer_deleted_root(repo_root, target_root_rel, changed.old_path)
            if deleted_root is not None and deleted_root not in targets_by_root:
                deleted_roots.add(deleted_root)

    return ChangedSkillSelection(
        repo_root=repo_root,
        target_root=resolved_target_root,
        base_ref=resolved_base,
        head_ref=head_ref or "HEAD",
        targets=tuple(sorted(targets_by_root.values(), key=lambda item: item.root.as_posix())),
        deleted_roots=tuple(sorted(deleted_roots, key=lambda item: item.as_posix())),
    )


def _merge_paths(
    existing: ChangedSkillTarget | None,
    old_path: Path | None,
    new_path: Path | None,
) -> tuple[Path, ...]:
    merged: list[Path] = list(existing.changed_paths) if existing is not None else []
    for path in (old_path, new_path):
        if path is not None and path not in merged:
            merged.append(path)
    return tuple(merged)


def _resolve_candidate_root(
    repo_root: Path,
    target_root_rel: Path,
    target_root: Path,
    rel_path: Path | None,
) -> Path | None:
    if rel_path is None:
        return None
    try:
        rel_path.relative_to(target_root_rel)
    except ValueError:
        return None
    abs_path = (repo_root / rel_path).resolve()
    if _is_relative_to(abs_path, target_root):
        resolved_root = find_skill_root(abs_path)
        if resolved_root is not None:
            return resolved_root
    return _infer_deleted_root(repo_root, target_root_rel, rel_path)


def _infer_deleted_root(repo_root: Path, target_root_rel: Path, rel_path: Path) -> Path | None:
    try:
        relative_to_target = rel_path.relative_to(target_root_rel)
    except ValueError:
        return None
    if not relative_to_target.parts:
        return None
    return repo_root / target_root_rel / relative_to_target.parts[0]


def _git_repo_root(path: Path) -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path.resolve(),
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(proc.stdout.strip()).resolve()


def _default_base_ref(repo_root: Path, head_ref: str) -> str:
    for upstream in ("origin/HEAD", "origin/main", "origin/master"):
        proc = subprocess.run(
            ["git", "merge-base", upstream, head_ref],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    return "HEAD"


def _git_diff_name_status(repo_root: Path, base_ref: str | None, head_ref: str) -> list[ChangedPath]:
    command = ["git", "diff", "--name-status", "-z"]
    if base_ref:
        command.append(f"{base_ref}...{head_ref}")
    else:
        command.append(head_ref)

    proc = subprocess.run(
        command,
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    raw = proc.stdout.decode("utf-8", errors="replace")
    if not raw:
        return []

    tokens = [token for token in raw.split("\x00") if token]
    entries: list[ChangedPath] = []
    index = 0
    while index < len(tokens):
        status = tokens[index]
        index += 1
        if status.startswith("R") or status.startswith("C"):
            entries.append(
                ChangedPath(
                    status=status,
                    old_path=Path(tokens[index]),
                    new_path=Path(tokens[index + 1]),
                )
            )
            index += 2
            continue

        path = Path(tokens[index])
        index += 1
        if status.startswith("D"):
            entries.append(ChangedPath(status=status, old_path=path, new_path=None))
        else:
            entries.append(ChangedPath(status=status, old_path=None, new_path=path))
    return entries


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False
