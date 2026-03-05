"""
SKILL.md parser — converts a skill directory into a ParsedSkill object.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML

from skill_gate.models import (
    EvalConfig,
    EvalExpectation,
    EvalTest,
    ParsedSkill,
    SkillMetadata,
    SkillParseError,
)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def parse_skill(skill_path: Path) -> ParsedSkill:
    """
    Parse a skill directory into a ParsedSkill object.

    Args:
        skill_path: Path to the skill directory.

    Returns:
        ParsedSkill with all fields populated.

    Raises:
        SkillParseError: If the skill directory is invalid or cannot be parsed.
    """
    skill_path = skill_path.resolve()

    if not skill_path.exists():
        raise SkillParseError(
            f"Skill directory not found: '{skill_path}'\n"
            f"  → Check the path and try again"
        )

    if not skill_path.is_dir():
        raise SkillParseError(
            f"'{skill_path}' is not a directory\n"
            f"  → Provide the path to the skill directory, not SKILL.md directly"
        )

    skill_md_path = skill_path / "SKILL.md"
    if not skill_md_path.exists():
        raise SkillParseError(
            f"SKILL.md not found in '{skill_path}'\n"
            f"  → Every skill directory must contain a SKILL.md file"
        )

    # Read and normalize line endings
    try:
        raw_content = skill_md_path.read_text(encoding="utf-8")
    except Exception as e:
        raise SkillParseError(f"Cannot read SKILL.md: {e}") from e

    # Normalize CRLF → LF
    content = raw_content.replace("\r\n", "\n").replace("\r", "\n")

    # Extract frontmatter and body
    metadata, body = _parse_frontmatter(content, skill_md_path)

    # Scan directory structure
    scripts_dir = skill_path / "scripts"
    references_dir = skill_path / "references"
    assets_dir = skill_path / "assets"
    evals_dir = skill_path / "evals"

    has_scripts = scripts_dir.is_dir()
    has_references = references_dir.is_dir()
    has_assets = assets_dir.is_dir()
    has_evals = evals_dir.is_dir()

    scripts = list(scripts_dir.iterdir()) if has_scripts else []
    scripts = [p for p in scripts if p.is_file()]

    references = list(references_dir.iterdir()) if has_references else []
    references = [p for p in references if p.is_file()]

    # Parse evals if present
    evals_config: Optional[EvalConfig] = None
    if has_evals:
        evals_config = _parse_evals_config(evals_dir)

    body_lines = body.splitlines()
    body_line_count = len([ln for ln in body_lines if ln.strip()])  # non-empty lines

    return ParsedSkill(
        path=skill_path,
        skill_md_path=skill_md_path,
        metadata=metadata,
        body=body,
        body_line_count=len(body_lines),
        has_scripts=has_scripts,
        scripts=scripts,
        has_references=has_references,
        references=references,
        has_assets=has_assets,
        has_evals=has_evals,
        evals_config=evals_config,
    )


def _parse_frontmatter(content: str, skill_md_path: Path) -> tuple[SkillMetadata, str]:
    """Extract and parse YAML frontmatter from SKILL.md content."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        # Check if file starts with --- at all
        if content.startswith("---"):
            raise SkillParseError(
                f"Unclosed frontmatter in '{skill_md_path}'\n"
                f"  → Add a closing '---' line after the frontmatter YAML"
            )
        raise SkillParseError(
            f"No YAML frontmatter found in '{skill_md_path}'\n"
            f"  → SKILL.md must start with '---' frontmatter block\n"
            f"  → Example:\n"
            f"     ---\n"
            f"     name: my-skill\n"
            f"     description: \"What this skill does. Use when...\"\n"
            f"     ---"
        )

    frontmatter_str = match.group(1)
    body = match.group(2)

    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        raw = yaml.load(frontmatter_str)
    except Exception as e:
        raise SkillParseError(
            f"Invalid YAML frontmatter in '{skill_md_path}': {e}\n"
            f"  → Check indentation, quotes, and special characters"
        ) from e

    if not raw or not isinstance(raw, dict):
        raise SkillParseError(
            f"Empty or invalid frontmatter in '{skill_md_path}'\n"
            f"  → frontmatter must contain at least 'name' and 'description' fields"
        )

    # Convert ruamel CommentedMap to plain dict
    raw_dict = _to_plain_dict(raw)

    # Validate required fields
    if "name" not in raw_dict:
        raise SkillParseError(
            f"Missing required field 'name' in '{skill_md_path}'\n"
            f"  → Add: name: your-skill-name"
        )
    if "description" not in raw_dict:
        raise SkillParseError(
            f"Missing required field 'description' in '{skill_md_path}'\n"
            f"  → Add: description: \"What this skill does. Use when...\""
        )

    try:
        metadata = SkillMetadata.model_validate(raw_dict)
    except Exception as e:
        raise SkillParseError(
            f"Invalid frontmatter fields in '{skill_md_path}': {e}"
        ) from e

    return metadata, body.strip()


def _parse_evals_config(evals_dir: Path) -> EvalConfig:
    """Parse evals/config.yaml into EvalConfig."""
    config_path = evals_dir / "config.yaml"
    if not config_path.exists():
        raise SkillParseError(
            f"evals/config.yaml not found in '{evals_dir.parent}'\n"
            f"  → Create evals/config.yaml with test case definitions\n"
            f"  → See docs/eval-authoring-guide.md for the format"
        )

    yaml = YAML()
    try:
        with open(config_path) as f:
            raw = yaml.load(f)
    except Exception as e:
        raise SkillParseError(
            f"Invalid YAML in '{config_path}': {e}"
        ) from e

    if not raw or "tests" not in raw:
        raise SkillParseError(
            f"'{config_path}' must contain a 'tests' list"
        )

    raw_dict = _to_plain_dict(raw)
    try:
        return EvalConfig.model_validate(raw_dict)
    except Exception as e:
        raise SkillParseError(
            f"Invalid evals/config.yaml in '{evals_dir.parent}': {e}"
        ) from e


def _to_plain_dict(obj: object) -> object:
    """Convert ruamel.yaml CommentedMap/Seq to plain Python types."""
    if hasattr(obj, "items"):
        return {k: _to_plain_dict(v) for k, v in obj.items()}
    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        return [_to_plain_dict(item) for item in obj]
    return obj
