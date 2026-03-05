"""Catalog management helpers."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from skill_guard.models import Catalog, CatalogEntry, ParsedSkill, ValidationResult


class CatalogManager:
    """Read/write and query skill catalogs."""

    def __init__(self) -> None:
        self._yaml = YAML()
        self._yaml.default_flow_style = False
        self._yaml.indent(mapping=2, sequence=4, offset=2)

    def load_catalog(self, path: Path) -> Catalog:
        """Load a catalog from disk; return an empty catalog if missing."""
        if not path.exists():
            return Catalog(updated=datetime.now(UTC), skills=[])

        with path.open(encoding="utf-8") as f:
            raw = self._yaml.load(f) or {}

        if not isinstance(raw, dict):
            raw = {}
        raw.setdefault("updated", datetime.now(UTC).isoformat())
        raw.setdefault("skills", [])
        return Catalog.model_validate(raw)

    def save_catalog(self, catalog: Catalog, path: Path) -> None:
        """Write catalog with an atomic temp-file swap."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".yaml.tmp")
        data: dict[str, Any] = catalog.model_dump(mode="json")

        with tmp_path.open("w", encoding="utf-8") as f:
            self._yaml.dump(data, f)

        os.replace(tmp_path, path)

    def register_skill(
        self,
        skill: ParsedSkill,
        validation_result: ValidationResult,
        path: Path,
    ) -> CatalogEntry:
        """Insert or update one skill entry and persist catalog."""
        catalog = self.load_catalog(path)
        now = datetime.now(UTC)
        existing = next(
            (entry for entry in catalog.skills if entry.name == skill.metadata.name), None
        )

        if existing is not None:
            existing.description = skill.metadata.description
            existing.author = skill.metadata.author or "unknown"
            existing.version = skill.metadata.version or "0.0.0"
            existing.last_updated = now
            existing.quality_score = validation_result.score
            existing.path = str(skill.path)
            existing.tags = skill.metadata.tags
            entry = existing
        else:
            entry = CatalogEntry(
                name=skill.metadata.name,
                description=skill.metadata.description,
                author=skill.metadata.author or "unknown",
                version=skill.metadata.version or "0.0.0",
                stage="staging",
                registered=now,
                last_updated=now,
                quality_score=validation_result.score,
                path=str(skill.path),
                tags=skill.metadata.tags,
            )
            catalog.skills.append(entry)

        catalog.updated = now
        self.save_catalog(catalog, path)
        return entry

    def list_skills(
        self,
        catalog: Catalog,
        stage: str | None = None,
        author: str | None = None,
        tag: str | None = None,
    ) -> list[CatalogEntry]:
        """List catalog entries with optional filters."""
        entries = catalog.skills
        if stage:
            entries = [entry for entry in entries if entry.stage == stage]
        if author:
            entries = [entry for entry in entries if entry.author.lower() == author.lower()]
        if tag:
            entries = [entry for entry in entries if tag in entry.tags]
        return entries

    def search_skills(self, catalog: Catalog, query: str) -> list[CatalogEntry]:
        """Search by substring in name or description."""
        q = query.lower().strip()
        return [
            entry
            for entry in catalog.skills
            if q in entry.name.lower() or q in entry.description.lower()
        ]

    def get_stats(self, catalog: Catalog) -> dict[str, int]:
        """Return stage counts and total."""
        stats = {
            "staging": 0,
            "production": 0,
            "degraded": 0,
            "deprecated": 0,
            "total": len(catalog.skills),
        }
        for entry in catalog.skills:
            stats[entry.stage] = stats.get(entry.stage, 0) + 1
        return stats
