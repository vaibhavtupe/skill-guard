"""
Conflict detection — TF-IDF similarity engine (Phase 1).
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Literal

from ruamel.yaml import YAML
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from skill_guard.config import ConflictConfig
from skill_guard.models import (
    ConfigError,
    ConflictMatch,
    ConflictResult,
    ParsedSkill,
    SkillParseError,
)
from skill_guard.parser import parse_skill

_TRIGGER_RE = re.compile(r"use when[^.]+\.?", re.IGNORECASE)


def compute_similarity(
    new_skill: ParsedSkill,
    existing_source: Path,
    config: ConflictConfig,
    method: Literal["tfidf", "embeddings", "llm"] | None = None,
    threshold: float | None = None,
) -> ConflictResult:
    """Compute similarity between new_skill and existing skills."""
    method = method or config.method
    threshold = threshold or config.similarity_threshold

    if method == "embeddings":
        return _compute_embeddings_similarity(new_skill, existing_source, config, threshold)
    if method == "llm":
        raise ConfigError(
            "LLM conflict detection is not yet implemented. Use method: tfidf (default)."
        )

    # Apply threshold override (treat as medium threshold)
    medium_threshold = threshold if threshold is not None else config.medium_overlap_threshold

    # Load existing skills
    existing_skills = _load_existing_skills(existing_source)

    # Exclude self-comparison
    existing_skills = [s for s in existing_skills if s.metadata.name != new_skill.metadata.name]

    matches: list[ConflictMatch] = []
    name_collision = False
    name_collision_with = None

    for existing in existing_skills:
        # Name collision check
        if existing.metadata.name == new_skill.metadata.name:
            name_collision = True
            name_collision_with = existing.metadata.name
        else:
            ratio = _levenshtein_ratio(existing.metadata.name, new_skill.metadata.name)
            if ratio >= 0.8:  # roughly equivalent to edit distance < 3 for short names
                name_collision = True
                name_collision_with = existing.metadata.name

        score = _tfidf_similarity(new_skill.metadata.description, existing.metadata.description)

        if score < medium_threshold:
            continue

        severity = "high" if score >= config.high_overlap_threshold else "medium"
        overlap_phrases = _extract_overlap_phrases(
            new_skill.metadata.description, existing.metadata.description
        )
        suggestions = [
            "Merge into a single skill with broader scope",
            "Narrow descriptions to distinguish triggers",
            "Add exclusion hints (e.g., 'Do NOT use for ...')",
        ]

        matches.append(
            ConflictMatch(
                existing_skill_name=existing.metadata.name,
                similarity_score=round(score, 2),
                severity=severity,  # type: ignore
                overlapping_phrases=overlap_phrases,
                suggestions=suggestions,
            )
        )

    high_conflicts = sum(1 for m in matches if m.severity == "high")
    medium_conflicts = sum(1 for m in matches if m.severity == "medium")

    passed = not (config.block_on_high_overlap and high_conflicts > 0)

    return ConflictResult(
        skill_name=new_skill.metadata.name,
        matches=matches,
        name_collision=name_collision,
        name_collision_with=name_collision_with,
        passed=passed,
        high_conflicts=high_conflicts,
        medium_conflicts=medium_conflicts,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_embeddings_similarity(
    new_skill: ParsedSkill,
    existing_source: Path,
    config: ConflictConfig,
    threshold: float | None = None,
) -> ConflictResult:
    """Embeddings-based conflict detection using sentence-transformers."""
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]
        from sklearn.metrics.pairwise import cosine_similarity as cos_sim
    except ImportError as exc:
        raise ConfigError(
            "sentence-transformers is required for embeddings conflict detection.\n"
            "Install with: pip install skill-guard[embeddings]"
        ) from exc

    medium_threshold = threshold if threshold is not None else config.medium_overlap_threshold
    existing_skills = _load_existing_skills(existing_source)
    existing_skills = [s for s in existing_skills if s.metadata.name != new_skill.metadata.name]

    model = SentenceTransformer("all-MiniLM-L6-v2")

    new_text = new_skill.metadata.description
    new_emb = model.encode([new_text])

    matches: list[ConflictMatch] = []
    name_collision = False
    name_collision_with = None

    for existing in existing_skills:
        if existing.metadata.name == new_skill.metadata.name:
            name_collision = True
            name_collision_with = existing.metadata.name
        else:
            ratio = _levenshtein_ratio(existing.metadata.name, new_skill.metadata.name)
            if ratio >= 0.8:
                name_collision = True
                name_collision_with = existing.metadata.name

        existing_emb = model.encode([existing.metadata.description])
        score = float(cos_sim(new_emb, existing_emb)[0][0])

        if score < medium_threshold:
            continue

        severity = "high" if score >= config.high_overlap_threshold else "medium"
        overlap_phrases = _extract_overlap_phrases(
            new_skill.metadata.description, existing.metadata.description
        )
        matches.append(
            ConflictMatch(
                existing_skill_name=existing.metadata.name,
                similarity_score=round(score, 2),
                severity=severity,  # type: ignore
                overlapping_phrases=overlap_phrases,
                suggestions=[
                    "Merge into a single skill with broader scope",
                    "Narrow descriptions to distinguish triggers",
                    "Add exclusion hints (e.g., 'Do NOT use for ...')",
                ],
            )
        )

    high_conflicts = sum(1 for m in matches if m.severity == "high")
    medium_conflicts = sum(1 for m in matches if m.severity == "medium")
    passed = not (config.block_on_high_overlap and high_conflicts > 0)

    return ConflictResult(
        skill_name=new_skill.metadata.name,
        matches=matches,
        name_collision=name_collision,
        name_collision_with=name_collision_with,
        passed=passed,
        high_conflicts=high_conflicts,
        medium_conflicts=medium_conflicts,
    )


def _tfidf_similarity(text_a: str, text_b: str) -> float:
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    tfidf = vectorizer.fit_transform([text_a, text_b])
    return cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]


def _extract_overlap_phrases(text_a: str, text_b: str) -> list[str]:
    """Extract overlapping phrases between two descriptions."""
    # naive approach: shared bigrams
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)

    bigrams_a = set(zip(tokens_a, tokens_a[1:], strict=False))
    bigrams_b = set(zip(tokens_b, tokens_b[1:], strict=False))

    overlap = bigrams_a.intersection(bigrams_b)
    phrases = [" ".join(b) for b in overlap]

    # Return top 3 phrases by length
    phrases = sorted(set(phrases), key=lambda s: (-len(s), s))
    return phrases[:3]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _levenshtein_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _load_existing_skills(source: Path) -> list[ParsedSkill]:
    """Load existing skills from directory or catalog YAML."""
    source = source.resolve()

    if source.is_dir():
        skills: list[ParsedSkill] = []
        for child in source.iterdir():
            if not child.is_dir():
                continue
            try:
                skills.append(parse_skill(child))
            except SkillParseError:
                continue
        return skills

    if source.is_file() and source.suffix in (".yaml", ".yml"):
        yaml = YAML()
        with open(source) as f:
            raw = yaml.load(f)
        skills = []
        for entry in raw.get("skills", []):
            # Create ParsedSkill-like object with only metadata
            meta = {
                "name": entry.get("name"),
                "description": entry.get("description"),
                "metadata": {
                    "author": entry.get("author"),
                    "version": entry.get("version"),
                    "tags": entry.get("tags", []),
                },
            }
            fake = ParsedSkill(
                path=source,
                skill_md_path=source,
                metadata=meta,  # pydantic will coerce to SkillMetadata
                body="",
                body_line_count=0,
                has_scripts=False,
                scripts=[],
                has_references=False,
                references=[],
                has_assets=False,
                has_evals=False,
                evals_config=None,
            )
            skills.append(fake)
        return skills

    raise SkillParseError(f"Invalid --against source: {source}")
