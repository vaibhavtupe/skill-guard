from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skill_guard.engine.catalog_manager import CatalogManager
from skill_guard.models import Catalog, CatalogEntry, CheckResult, ValidationResult
from skill_guard.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def _validation_result(skill_name: str, score: int = 90) -> ValidationResult:
    return ValidationResult(
        skill_name=skill_name,
        skill_path=Path("/tmp/skill"),
        checks=[CheckResult(check_name="shape", passed=True, severity="info", message="ok")],
        score=score,
        grade="A",
        passed=True,
        warnings=0,
        blockers=0,
    )


def _entry(name: str, stage: str) -> CatalogEntry:
    now = datetime.now(UTC)
    return CatalogEntry(
        name=name,
        description=f"{name} description",
        author="author",
        version="1.0.0",
        stage=stage,  # type: ignore[arg-type]
        registered=now,
        last_updated=now,
        quality_score=95,
        path=f"/tmp/{name}",
        tags=["ops"],
    )


def test_empty_catalog_loads_ok(tmp_path: Path) -> None:
    manager = CatalogManager()
    catalog = manager.load_catalog(tmp_path / "missing.yaml")
    assert catalog.skills == []


def test_register_creates_entry_with_stage_staging(tmp_path: Path) -> None:
    manager = CatalogManager()
    catalog_path = tmp_path / "catalog.yaml"
    skill = parse_skill(FIXTURES / "valid-skill")

    entry = manager.register_skill(skill, _validation_result(skill.metadata.name), catalog_path)

    assert entry.stage == "staging"
    loaded = manager.load_catalog(catalog_path)
    assert len(loaded.skills) == 1


def test_register_updates_existing_entry(tmp_path: Path) -> None:
    manager = CatalogManager()
    catalog_path = tmp_path / "catalog.yaml"
    skill = parse_skill(FIXTURES / "valid-skill")

    manager.register_skill(skill, _validation_result(skill.metadata.name, score=70), catalog_path)
    updated_skill = skill.model_copy(deep=True)
    updated_skill.metadata.description = "Updated description"
    manager.register_skill(
        updated_skill,
        _validation_result(updated_skill.metadata.name, score=99),
        catalog_path,
    )

    loaded = manager.load_catalog(catalog_path)
    assert len(loaded.skills) == 1
    assert loaded.skills[0].description == "Updated description"
    assert loaded.skills[0].quality_score == 99


def test_list_skills_filters_by_stage(tmp_path: Path) -> None:
    manager = CatalogManager()
    catalog = Catalog(
        updated=datetime.now(UTC),
        skills=[_entry("alpha", "staging"), _entry("beta", "production")],
    )
    manager.save_catalog(catalog, tmp_path / "catalog.yaml")

    results = manager.list_skills(catalog, stage="production")
    assert len(results) == 1
    assert results[0].name == "beta"


def test_search_skills_finds_by_name_substring(tmp_path: Path) -> None:
    manager = CatalogManager()
    catalog = Catalog(
        updated=datetime.now(UTC),
        skills=[_entry("incident-responder", "staging"), _entry("billing-audit", "production")],
    )
    manager.save_catalog(catalog, tmp_path / "catalog.yaml")

    results = manager.search_skills(catalog, "respon")
    assert len(results) == 1
    assert results[0].name == "incident-responder"


def test_get_stats_returns_correct_counts() -> None:
    manager = CatalogManager()
    catalog = Catalog(
        updated=datetime.now(UTC),
        skills=[
            _entry("a", "staging"),
            _entry("b", "staging"),
            _entry("c", "production"),
            _entry("d", "deprecated"),
        ],
    )

    stats = manager.get_stats(catalog)
    assert stats["total"] == 4
    assert stats["staging"] == 2
    assert stats["production"] == 1
    assert stats["deprecated"] == 1


def test_atomic_save_file_exists_after_save(tmp_path: Path) -> None:
    manager = CatalogManager()
    catalog = Catalog(updated=datetime.now(UTC), skills=[])
    catalog_path = tmp_path / "catalog.yaml"

    manager.save_catalog(catalog, catalog_path)

    assert catalog_path.exists()


def test_increment_eval_count_updates_entry() -> None:
    manager = CatalogManager()
    entry = _entry("alpha", "production")

    manager.increment_eval_count(entry)

    assert entry.eval_count == 1
