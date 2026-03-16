from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from skill_guard.config import MonitorConfig
from skill_guard.engine.lifecycle import apply_stage_transitions, check_ownership, check_staleness
from skill_guard.models import CatalogEntry


def _entry(stage: str = "production", failures: int = 0) -> CatalogEntry:
    now = datetime.now(UTC)
    return CatalogEntry(
        name="alpha",
        description="desc",
        author="owner@example.com",
        version="1.0.0",
        stage=stage,  # type: ignore[arg-type]
        registered=now,
        last_updated=now,
        quality_score=95,
        path="/tmp/alpha",
        consecutive_eval_failures=failures,
    )


def test_apply_stage_transitions_production_to_degraded() -> None:
    cfg = MonitorConfig(degrade_after_failures=7, deprecate_after_failures=30)
    updated, msgs = apply_stage_transitions(_entry(stage="production", failures=7), cfg, Path("."))
    assert updated.stage == "degraded"
    assert any("production -> degraded" in msg for msg in msgs)
    assert any("degrade_after_failures=7" in msg for msg in msgs)


def test_apply_stage_transitions_degraded_to_deprecated() -> None:
    cfg = MonitorConfig(degrade_after_failures=7, deprecate_after_failures=30)
    updated, msgs = apply_stage_transitions(_entry(stage="degraded", failures=30), cfg, Path("."))
    assert updated.stage == "deprecated"
    assert any("degraded -> deprecated" in msg for msg in msgs)
    assert any("deprecate_after_failures=30" in msg for msg in msgs)


def test_check_staleness_warns_when_old() -> None:
    entry = _entry()
    entry.last_updated = datetime.now(UTC) - timedelta(days=181)
    warning = check_staleness(entry, threshold_days=180)
    assert warning is not None
    assert "stale skill" in warning


def test_check_staleness_none_when_recent() -> None:
    assert check_staleness(_entry(), threshold_days=180) is None


def test_check_ownership_missing_owner_in_file(tmp_path: Path) -> None:
    (tmp_path / "CODEOWNERS").write_text("* @another-owner\n", encoding="utf-8")
    warning = check_ownership(_entry(), tmp_path, ["CODEOWNERS", "MAINTAINERS"], fallback="warn")
    assert warning is not None
    assert "not found" in warning


def test_check_ownership_warns_when_file_missing_and_warn_fallback(tmp_path: Path) -> None:
    warning = check_ownership(_entry(), tmp_path, ["CODEOWNERS"], fallback="warn")
    assert warning is not None
    assert "missing" in warning


def test_check_ownership_skips_when_file_missing_and_skip_fallback(tmp_path: Path) -> None:
    warning = check_ownership(_entry(), tmp_path, ["CODEOWNERS"], fallback="skip")
    assert warning is None
