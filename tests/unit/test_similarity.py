import builtins
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from skill_guard.config import ConflictConfig
from skill_guard.engine import similarity
from skill_guard.engine.similarity import compute_similarity
from skill_guard.models import ConfigError
from skill_guard.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_conflict_high_overlap():
    new_skill = parse_skill(FIXTURES / "conflicting-skill")
    result = compute_similarity(new_skill, FIXTURES, ConflictConfig())
    assert result.high_conflicts >= 1 or result.medium_conflicts >= 1


def test_conflict_self_excluded():
    new_skill = parse_skill(FIXTURES / "valid-skill")
    result = compute_similarity(new_skill, FIXTURES, ConflictConfig())
    assert all(m.existing_skill_name != "valid-skill" for m in result.matches)


def test_embeddings_mode_uses_cache_and_cosine_similarity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    encode_calls: list[str] = []
    cosine_calls: list[tuple[list[float], list[float]]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            assert model_name == "all-MiniLM-L6-v2"

        def encode(self, text: str) -> list[float]:
            encode_calls.append(text)
            if "weather" in text.lower():
                return [1.0, 0.0]
            return [0.8, 0.2]

    def fake_cosine(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        cosine_calls.append((vec_a.tolist(), vec_b.tolist()))
        return float(np.dot(vec_a, vec_b))

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    monkeypatch.setattr(similarity, "_cosine_similarity", fake_cosine)

    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(
        (
            "skills:\n"
            "  - name: weather-helper\n"
            "    description: Use when the user needs weather forecasts or current conditions.\n"
        ),
        encoding="utf-8",
    )
    config = ConflictConfig(
        method="embeddings",
        similarity_threshold=0.1,
        embeddings_cache_dir=str(tmp_path / "embeddings-cache"),
    )
    new_skill = parse_skill(FIXTURES / "valid-skill")

    first_result = compute_similarity(new_skill, catalog_path, config)
    second_result = compute_similarity(new_skill, catalog_path, config)

    assert first_result.matches
    assert second_result.matches
    assert len(encode_calls) == 2
    assert cosine_calls

    cache_files = sorted((tmp_path / "embeddings-cache").glob("*.json"))
    assert len(cache_files) == 2
    with cache_files[0].open(encoding="utf-8") as handle:
        payload = json.load(handle)
    assert "embedding" in payload


def test_llm_mode_builds_prompt_and_parses_yes_no(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts: list[str] = []

    class FakeCompletions:
        async def create(self, *, model: str, messages: list[dict[str, str]]):
            assert model == "gpt-4o-mini"
            assert messages[0]["role"] == "user"
            prompt = messages[0]["content"]
            prompts.append(prompt)
            reply = "YES" if "email" in prompt.lower() else "NO"
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=reply))]
            )

    class FakeAsyncOpenAI:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-key"
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))

    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(
        (
            "skills:\n"
            "  - name: email-helper\n"
            "    description: Use when the user needs help drafting or editing email messages.\n"
            "  - name: weather-helper\n"
            "    description: Use when the user needs weather forecasts or current conditions.\n"
        ),
        encoding="utf-8",
    )
    config = ConflictConfig(method="llm", similarity_threshold=0.5)
    new_skill = parse_skill(FIXTURES / "valid-skill")

    result = compute_similarity(new_skill, catalog_path, config)

    assert len(prompts) == 2
    assert prompts[0].startswith(
        "Do these two agent skills overlap in purpose or trigger? Answer YES or NO only."
    )
    assert "\n\nSkill A: " in prompts[0]
    assert "\n\nSkill B: " in prompts[0]
    assert [match.existing_skill_name for match in result.matches] == ["email-helper"]
    assert result.matches[0].similarity_score == 0.85


@pytest.mark.parametrize(
    ("method", "message", "env"),
    [
        (
            "embeddings",
            "Embeddings extra not installed: pip install skill-guard[embeddings]",
            {},
        ),
        (
            "llm",
            "LLM extra not installed: pip install skill-guard[llm]",
            {"OPENAI_API_KEY": "test-key"},
        ),
    ],
)
def test_conflict_missing_optional_extra_raises_config_error(
    method: str, message: str, env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name in {"sentence_transformers", "openai"}:
            raise ImportError("missing optional dependency")
        return original_import(name, *args, **kwargs)

    for key in ("OPENAI_API_KEY",):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    new_skill = parse_skill(FIXTURES / "valid-skill")

    with pytest.raises(ConfigError, match=re.escape(message)):
        compute_similarity(new_skill, FIXTURES, ConflictConfig(method=method))


def test_llm_mode_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    new_skill = parse_skill(FIXTURES / "valid-skill")

    with pytest.raises(ConfigError, match="OPENAI_API_KEY env var not set"):
        compute_similarity(new_skill, FIXTURES, ConflictConfig(method="llm"))
