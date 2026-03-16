"""
Conflict detection similarity engine.
"""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

import numpy as np
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
_EMBEDDINGS_MODEL_NAME = "all-MiniLM-L6-v2"
_LLM_TIMEOUT_SECONDS = 30


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

    # Apply threshold override (treat as medium threshold)
    medium_threshold = threshold if threshold is not None else config.medium_overlap_threshold

    existing_skills = _load_existing_skills(existing_source)
    existing_skills = [s for s in existing_skills if s.metadata.name != new_skill.metadata.name]

    scores: list[tuple[ParsedSkill, float]]
    if method == "tfidf":
        scores = [
            (
                existing,
                _tfidf_similarity(new_skill.metadata.description, existing.metadata.description),
            )
            for existing in existing_skills
        ]
    elif method == "embeddings":
        scores = _embeddings_similarity(new_skill, existing_skills, config)
    elif method == "llm":
        scores = asyncio.run(_llm_similarity(new_skill, existing_skills, config))
    else:
        raise ConfigError(f"Unsupported conflict detection method: {method}")

    matches: list[ConflictMatch] = []
    name_collision = False
    name_collision_with = None

    for existing, score in scores:
        if existing.metadata.name == new_skill.metadata.name:
            name_collision = True
            name_collision_with = existing.metadata.name
        else:
            ratio = _levenshtein_ratio(existing.metadata.name, new_skill.metadata.name)
            if ratio >= 0.8:
                name_collision = True
                name_collision_with = existing.metadata.name

        if score < medium_threshold:
            continue

        if score >= config.high_overlap_threshold:
            severity = "high"
        elif score >= config.medium_overlap_threshold:
            severity = "medium"
        else:
            severity = "low"

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
                severity=severity,
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


def _tfidf_similarity(text_a: str, text_b: str) -> float:
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    tfidf = vectorizer.fit_transform([text_a, text_b])
    return cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]


def _embeddings_similarity(
    new_skill: ParsedSkill,
    existing_skills: list[ParsedSkill],
    config: ConflictConfig,
) -> list[tuple[ParsedSkill, float]]:
    if not existing_skills:
        return []

    model = _load_sentence_transformer()
    cache_dir = Path(config.embeddings_cache_dir)
    new_embedding = _get_cached_embedding(
        model, cache_dir, new_skill.metadata.name, new_skill.metadata.description
    )

    scores: list[tuple[ParsedSkill, float]] = []
    for existing in existing_skills:
        existing_embedding = _get_cached_embedding(
            model, cache_dir, existing.metadata.name, existing.metadata.description
        )
        scores.append((existing, _cosine_similarity(new_embedding, existing_embedding)))
    return scores


def _load_sentence_transformer() -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ConfigError(
            "Embeddings extra not installed: pip install skill-guard[embeddings]"
        ) from exc

    return SentenceTransformer(_EMBEDDINGS_MODEL_NAME)


def _get_cached_embedding(
    model: Any, cache_dir: Path, skill_name: str, description: str
) -> np.ndarray:
    cache_file = cache_dir / f"{_embedding_cache_key(skill_name, description)}.json"
    if cache_file.exists():
        with cache_file.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return _normalize_embedding(np.asarray(payload["embedding"], dtype=float))

    embedding = _normalize_embedding(np.asarray(model.encode(description), dtype=float))
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with cache_file.open("w", encoding="utf-8") as handle:
        json.dump({"embedding": embedding.tolist()}, handle)
    return embedding


def _embedding_cache_key(skill_name: str, description: str) -> str:
    desc_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", skill_name).strip("-") or "skill"
    return f"{safe_name}-{desc_hash}"


def _normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(embedding)
    if norm == 0:
        return embedding
    return embedding / norm


def _cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    return float(np.dot(vec_a, vec_b))


async def _llm_similarity(
    new_skill: ParsedSkill,
    existing_skills: list[ParsedSkill],
    config: ConflictConfig,
) -> list[tuple[ParsedSkill, float]]:
    if not existing_skills:
        return []

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ConfigError("OPENAI_API_KEY env var not set")

    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise ConfigError("LLM extra not installed: pip install skill-guard[llm]") from exc

    client = AsyncOpenAI(api_key=api_key)
    semaphore = asyncio.Semaphore(config.llm_max_concurrent)

    async def _score(existing: ParsedSkill) -> tuple[ParsedSkill, float]:
        async with semaphore:
            prompt = _build_llm_prompt(
                new_skill.metadata.description, existing.metadata.description
            )
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=config.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=_LLM_TIMEOUT_SECONDS,
            )
            content = response.choices[0].message.content or ""
            return existing, _parse_llm_score(content)

    return list(await asyncio.gather(*(_score(existing) for existing in existing_skills)))


def _build_llm_prompt(desc_a: str, desc_b: str) -> str:
    return (
        "Do these two agent skills overlap in purpose or trigger? Answer YES or NO only.\n\n"
        f"Skill A: {desc_a}\n\n"
        f"Skill B: {desc_b}"
    )


def _parse_llm_score(content: str) -> float:
    answer = content.strip().upper()
    return 0.85 if answer.startswith("YES") else 0.1


def _extract_overlap_phrases(text_a: str, text_b: str) -> list[str]:
    """Extract overlapping phrases between two descriptions."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)

    bigrams_a = set(zip(tokens_a, tokens_a[1:], strict=False))
    bigrams_b = set(zip(tokens_b, tokens_b[1:], strict=False))

    overlap = bigrams_a.intersection(bigrams_b)
    phrases = [" ".join(bigram) for bigram in overlap]
    phrases.extend(_extract_trigger_phrase(text_a, text_b))

    phrases = sorted(set(phrases), key=lambda value: (-len(value), value))
    return phrases[:3]


def _extract_trigger_phrase(text_a: str, text_b: str) -> list[str]:
    trigger_a = _TRIGGER_RE.search(text_a)
    trigger_b = _TRIGGER_RE.search(text_b)
    if not trigger_a or not trigger_b:
        return []
    return [trigger_a.group(0)] if trigger_a.group(0).lower() == trigger_b.group(0).lower() else []


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
        with open(source, encoding="utf-8") as handle:
            raw = yaml.load(handle)
        skills = []
        for entry in raw.get("skills", []):
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
                metadata=meta,
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
