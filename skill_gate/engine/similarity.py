"""
Conflict detection — TF-IDF similarity engine (Phase 1).
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Iterable, Literal

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from ruamel.yaml import YAML

from skill_gate.config import ConflictConfig
from skill_gate.models import ConflictMatch, ConflictResult, ParsedSkill, SkillParseError
from skill_gate.parser import parse_skill

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
        raise NotImplementedError(
            "Embeddings method is not available in Phase 1. "
            "Install skill-gate[embeddings] and use Phase 3." 
        )
    if method == "llm":
        raise NotImplementedError(
            "LLM-based conflict detection is planned for Phase 3. "
            "Use method=tfidf in Phase 1."
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

def _tfidf_similarity(text_a: str, text_b: str) -> float:
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    tfidf = vectorizer.fit_transform([text_a, text_b])
    return cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]


def _extract_overlap_phrases(text_a: str, text_b: str) -> list[str]:
    """Extract overlapping phrases between two descriptions."""
    # naive approach: shared bigrams
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)

    bigrams_a = set(zip(tokens_a, tokens_a[1:]))
    bigrams_b = set(zip(tokens_b, tokens_b[1:]))

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
