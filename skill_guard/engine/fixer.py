"""Deterministic SKILL.md repair helpers."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML

from skill_guard.models import ParsedSkill

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_MARKDOWN_LINK_RE = re.compile(r"(?P<label>\[[^\]]+\])\((?P<path>[^)#]+)\)")
_TRIGGER_HINT_RE = re.compile(
    r"\b(use when|whenever|make sure to use|triggers on)\b", re.IGNORECASE
)


@dataclass
class FixPlan:
    description: str
    was_applied: bool = False
    reason_if_not: str | None = None
    apply_change: Callable[[str], str] | None = field(default=None, repr=False, compare=False)


def plan_fixes(parsed_skill: ParsedSkill | None, skill_path: Path) -> list[FixPlan]:
    """Plan deterministic repairs for a skill without mutating files."""
    skill_md_path = skill_path / "SKILL.md"
    raw_content = (
        skill_md_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    )
    match = _FRONTMATTER_RE.match(raw_content)
    if not match:
        return [
            FixPlan(
                description="Add YAML frontmatter to SKILL.md",
                reason_if_not="Manual fix required: SKILL.md is missing valid YAML frontmatter.",
            )
        ]

    yaml = YAML()
    yaml.preserve_quotes = True
    frontmatter = yaml.load(match.group(1)) or {}
    body = match.group(2)

    plans: list[FixPlan] = []
    plans.extend(_plan_frontmatter_fixes(frontmatter, yaml, body, raw_content, skill_path))
    plans.extend(_plan_body_fixes(frontmatter, yaml, body, raw_content))
    plans.extend(_plan_link_fixes(body, skill_path))
    plans.extend(_plan_semantic_reports(parsed_skill))
    return plans


def apply_fixes(skill_path: Path, fix_plans: list[FixPlan]) -> int:
    """Apply all applicable fixes atomically and return the applied fix count."""
    skill_md_path = skill_path / "SKILL.md"
    content = skill_md_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    applied = 0

    for plan in fix_plans:
        if plan.reason_if_not is not None or plan.apply_change is None:
            continue
        updated = plan.apply_change(content)
        if updated == content:
            continue
        content = updated
        plan.was_applied = True
        applied += 1

    tmp_path = skill_md_path.with_suffix(f"{skill_md_path.suffix}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(content)
    os.replace(tmp_path, skill_md_path)
    return applied


def _plan_frontmatter_fixes(
    frontmatter: dict,
    yaml: YAML,
    body: str,
    raw_content: str,
    skill_path: Path,
) -> list[FixPlan]:
    updates: list[tuple[str, tuple[str, ...], str]] = []
    if not str(frontmatter.get("name", "")).strip():
        updates.append(("Insert missing frontmatter key 'name'", ("name",), skill_path.name))
    if not str(frontmatter.get("description", "")).strip():
        updates.append(
            (
                "Insert missing frontmatter key 'description'",
                ("description",),
                "TODO: describe what this skill does. Use when <specific trigger>.",
            )
        )

    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    if not str(metadata.get("author", "")).strip():
        updates.append(
            ("Insert missing frontmatter key 'metadata.author'", ("metadata", "author"), "TODO")
        )
    if not str(metadata.get("version", "")).strip():
        updates.append(
            ("Insert missing frontmatter key 'metadata.version'", ("metadata", "version"), "TODO")
        )

    def make_apply(path_parts: tuple[str, ...], value: str) -> Callable[[str], str]:
        def _apply(content: str) -> str:
            current_frontmatter, current_body = _load_frontmatter_and_body(content, yaml)
            target = current_frontmatter
            for key in path_parts[:-1]:
                next_value = target.get(key)
                if not isinstance(next_value, dict):
                    next_value = {}
                    target[key] = next_value
                target = next_value
            if str(target.get(path_parts[-1], "")).strip():
                return content
            target[path_parts[-1]] = value
            return _render_skill_doc(current_frontmatter, current_body, yaml)

        return _apply

    return [
        FixPlan(description=description, apply_change=make_apply(path_parts, value))
        for description, path_parts, value in updates
    ]


def _plan_body_fixes(frontmatter: dict, yaml: YAML, body: str, raw_content: str) -> list[FixPlan]:
    plans: list[FixPlan] = []

    tab_fixed_lines = [line.replace("\t", "  ") for line in body.splitlines()]
    body_without_tabs = "\n".join(tab_fixed_lines)
    if body_without_tabs != body:
        plans.append(
            FixPlan(
                description="Convert tabs in SKILL.md body to 2 spaces",
                apply_change=lambda content: _rewrite_body(
                    content, yaml, lambda current: current.replace("\t", "  ")
                ),
            )
        )

    stripped_lines = [line.rstrip() for line in body.splitlines()]
    body_without_trailing_whitespace = "\n".join(stripped_lines)
    if body_without_trailing_whitespace != body:
        plans.append(
            FixPlan(
                description="Strip trailing whitespace from SKILL.md body lines",
                apply_change=lambda content: _rewrite_body(
                    content,
                    yaml,
                    lambda current: "\n".join(line.rstrip() for line in current.splitlines()),
                ),
            )
        )

    return plans


def _plan_link_fixes(body: str, skill_path: Path) -> list[FixPlan]:
    plans: list[FixPlan] = []
    for match in _MARKDOWN_LINK_RE.finditer(body):
        raw_path = match.group("path").strip()
        if raw_path.startswith(("http://", "https://", "#")):
            continue
        if (skill_path / raw_path).exists():
            continue

        candidates = _find_link_candidates(skill_path, raw_path)
        if len(candidates) == 1:
            label = match.group("label")
            replacement = f"{label}({candidates[0].as_posix()})"
            original = match.group(0)
            plans.append(
                FixPlan(
                    description=f"Rewrite broken relative link '{raw_path}'",
                    apply_change=lambda content, old=original, new=replacement: content.replace(
                        old, new, 1
                    ),
                )
            )
            continue

        if len(candidates) > 1:
            plans.append(
                FixPlan(
                    description=f"Resolve ambiguous relative link '{raw_path}'",
                    reason_if_not=(
                        "Manual fix required: broken relative links with multiple candidates are not auto-fixed."
                    ),
                )
            )

    return plans


def _plan_semantic_reports(parsed_skill: ParsedSkill | None) -> list[FixPlan]:
    if parsed_skill is None:
        return []

    description = parsed_skill.metadata.description.strip()
    if len(description.split()) >= 20 and _TRIGGER_HINT_RE.search(description):
        return []

    return [
        FixPlan(
            description="Improve semantic content in SKILL.md description",
            reason_if_not="Manual fix required: semantic content issues are not auto-fixed.",
        )
    ]


def _load_frontmatter_and_body(content: str, yaml: YAML) -> tuple[dict, str]:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content
    frontmatter = yaml.load(match.group(1)) or {}
    return frontmatter, match.group(2)


def _render_skill_doc(frontmatter: dict, body: str, yaml: YAML) -> str:
    buffer = StringIO()
    yaml.dump(frontmatter, buffer)
    rendered_body = body.rstrip()
    return f"---\n{buffer.getvalue()}---\n\n{rendered_body}\n"


def _rewrite_body(content: str, yaml: YAML, transform: Callable[[str], str]) -> str:
    frontmatter, body = _load_frontmatter_and_body(content, yaml)
    updated_body = transform(body)
    if updated_body == body:
        return content
    return _render_skill_doc(frontmatter, updated_body, yaml)


def _find_link_candidates(skill_path: Path, raw_path: str) -> list[Path]:
    basename = Path(raw_path).name
    matches: list[Path] = []
    for candidate in skill_path.rglob("*"):
        if not candidate.is_file() or candidate.name != basename:
            continue
        if candidate == skill_path / "SKILL.md":
            continue
        matches.append(candidate.relative_to(skill_path))
    return sorted(matches)
