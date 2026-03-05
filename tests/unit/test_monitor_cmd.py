from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from skill_guard.engine.catalog_manager import CatalogManager
from skill_guard.main import app
from skill_guard.models import Catalog, CatalogEntry

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def _entry(name: str, stage: str, path: str, failures: int = 0) -> CatalogEntry:
    now = datetime.now(UTC)
    return CatalogEntry(
        name=name,
        description="Use when you need a valid skill.",
        author="maintainer@example.com",
        version="1.0.0",
        stage=stage,  # type: ignore[arg-type]
        registered=now,
        last_updated=now,
        quality_score=95,
        path=path,
        consecutive_eval_failures=failures,
    )


def _write_config(path: Path, degrade_after: int = 7) -> None:
    path.write_text(
        (
            "monitor:\n"
            "  stale_threshold_days: 99999\n"
            f"  degrade_after_days: {degrade_after}\n"
            "  deprecate_after_days: 30\n"
            "  check_ownership: false\n"
        ),
        encoding="utf-8",
    )


def test_monitor_cmd_success_json_output(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    config_path = tmp_path / "skill-gate.yaml"
    manager = CatalogManager()
    skill_path = str((FIXTURES / "valid-skill").resolve())
    catalog = Catalog(
        updated=datetime.now(UTC),
        skills=[_entry("valid-skill", "production", skill_path)],
    )
    manager.save_catalog(catalog, catalog_path)
    _write_config(config_path)

    result = runner.invoke(
        app,
        [
            "monitor",
            "--catalog",
            str(catalog_path),
            "--config",
            str(config_path),
            "--static-only",
            "--repo-root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "monitor"
    assert payload["result"]["healthy"] == 1
    assert payload["result"]["failing"] == 0


def test_monitor_cmd_transitions_to_degraded_and_fails(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    config_path = tmp_path / "skill-gate.yaml"
    manager = CatalogManager()
    catalog = Catalog(
        updated=datetime.now(UTC),
        skills=[_entry("missing-skill", "production", "./missing-skill", failures=0)],
    )
    manager.save_catalog(catalog, catalog_path)
    _write_config(config_path, degrade_after=1)

    result = runner.invoke(
        app,
        [
            "monitor",
            "--catalog",
            str(catalog_path),
            "--config",
            str(config_path),
            "--static-only",
            "--repo-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    updated_catalog = manager.load_catalog(catalog_path)
    assert updated_catalog.skills[0].stage == "degraded"


def test_monitor_cmd_html_output(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    config_path = tmp_path / "skill-gate.yaml"
    manager = CatalogManager()
    skill_path = str((FIXTURES / "valid-skill").resolve())
    catalog = Catalog(
        updated=datetime.now(UTC),
        skills=[_entry("valid-skill", "production", skill_path)],
    )
    manager.save_catalog(catalog, catalog_path)
    _write_config(config_path)

    result = runner.invoke(
        app,
        [
            "monitor",
            "--catalog",
            str(catalog_path),
            "--config",
            str(config_path),
            "--static-only",
            "--repo-root",
            str(tmp_path),
            "--format",
            "html",
        ],
    )
    assert result.exit_code == 0
    assert "<html" in result.stdout
    assert "skill-gate monitor report" in result.stdout
