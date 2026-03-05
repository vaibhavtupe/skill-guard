"""Lifecycle monitoring helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skill_guard.config import MonitorConfig
from skill_guard.models import CatalogEntry


def apply_stage_transitions(
    entry: CatalogEntry, config: MonitorConfig, repo_root: Path
) -> tuple[CatalogEntry, list[str]]:
    """Apply phase 3 stage transitions based on consecutive failures."""
    _ = repo_root
    updated = entry.model_copy(deep=True)
    messages: list[str] = []
    original_stage = updated.stage
    failures = updated.consecutive_eval_failures

    if original_stage == "production" and failures >= config.degrade_after_days:
        updated.stage = "degraded"
        messages.append(
            f"{updated.name}: stage transitioned production -> degraded "
            f"(consecutive_eval_failures={failures})"
        )

    if updated.stage == "degraded" and failures >= config.deprecate_after_days:
        updated.stage = "deprecated"
        messages.append(
            f"{updated.name}: stage transitioned degraded -> deprecated "
            f"(consecutive_eval_failures={failures})"
        )

    return updated, messages


def check_staleness(entry: CatalogEntry, threshold_days: int) -> str | None:
    """Warn when skill has not been updated for threshold_days."""
    now = datetime.now(UTC)
    age_days = (now - entry.last_updated).days
    if age_days >= threshold_days:
        return (
            f"{entry.name}: stale skill (last_updated={entry.last_updated.date()}, "
            f"age_days={age_days}, threshold_days={threshold_days})"
        )
    return None


def check_ownership(
    entry: CatalogEntry,
    repo_root: Path,
    ownership_files: list[str],
    fallback: str,
) -> str | None:
    """Check whether entry author appears in CODEOWNERS/MAINTAINERS text."""
    for relative_name in ownership_files:
        ownership_path = repo_root / relative_name
        if not ownership_path.exists() or not ownership_path.is_file():
            continue

        try:
            text = ownership_path.read_text(encoding="utf-8")
        except Exception:
            continue

        if entry.author and entry.author in text:
            return None
        return f"{entry.name}: owner '{entry.author}' not found in ownership file '{relative_name}'"

    if fallback == "warn":
        return f"{entry.name}: ownership metadata file missing ({', '.join(ownership_files)})"
    return None
