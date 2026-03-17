import builtins
import re
import sys
import types
from pathlib import Path

import pytest

from skill_guard.config import ConflictConfig
from skill_guard.engine.similarity import compute_similarity
from skill_guard.models import ConfigError
from skill_guard.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def _install_fake_sentence_transformers(monkeypatch):
    module = types.ModuleType("sentence_transformers")

    class FakeSentenceTransformer:
        last_init = None

        def __init__(self, model_name, cache_folder=None):
            FakeSentenceTransformer.last_init = {
                "model_name": model_name,
                "cache_folder": cache_folder,
            }

        def encode(self, texts):
            vectors = []
            for text in texts:
                if "network" in text.lower():
                    vectors.append([1.0, 0.0])
                else:
                    vectors.append([0.0, 1.0])
            return vectors

    module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    return FakeSentenceTransformer


def test_conflict_high_overlap():
    new_skill = parse_skill(FIXTURES / "conflicting-skill")
    result = compute_similarity(new_skill, FIXTURES, ConflictConfig())
    assert result.high_conflicts >= 1 or result.medium_conflicts >= 1


def test_conflict_self_excluded():
    new_skill = parse_skill(FIXTURES / "valid-skill")
    result = compute_similarity(new_skill, FIXTURES, ConflictConfig())
    # Should not conflict with itself
    assert all(m.existing_skill_name != "valid-skill" for m in result.matches)


def test_conflict_ignore_skips_named_skill():
    new_skill = parse_skill(FIXTURES / "ignore-conflict-skill")
    result = compute_similarity(new_skill, FIXTURES, ConflictConfig())
    assert all(m.existing_skill_name != "conflicting-skill" for m in result.matches)


def test_conflict_embeddings_missing_dependency(monkeypatch) -> None:
    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "sentence_transformers":
            raise ImportError("missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)

    new_skill = parse_skill(FIXTURES / "valid-skill")
    with pytest.raises(
        ConfigError,
        match=re.escape("sentence-transformers is required for embeddings conflict detection."),
    ):
        compute_similarity(new_skill, FIXTURES, ConflictConfig(method="embeddings"))


def test_conflict_embeddings_similarity_uses_cache_and_model(
    monkeypatch, tmp_path, capsys
) -> None:
    fake_model = _install_fake_sentence_transformers(monkeypatch)
    new_skill = parse_skill(FIXTURES / "conflicting-skill")

    config = ConflictConfig(
        method="embeddings",
        embeddings_cache_dir=str(tmp_path),
        embeddings_model="all-MiniLM-L6-v2",
    )

    result = compute_similarity(
        new_skill,
        FIXTURES,
        config,
        embeddings_model="custom-model",
    )

    assert result.high_conflicts >= 1
    assert fake_model.last_init["model_name"] == "custom-model"
    assert fake_model.last_init["cache_folder"] == str(tmp_path)
    assert "Downloading model" in capsys.readouterr().err


def test_conflict_embeddings_offline_requires_cached_model(monkeypatch, tmp_path) -> None:
    _install_fake_sentence_transformers(monkeypatch)
    new_skill = parse_skill(FIXTURES / "conflicting-skill")

    config = ConflictConfig(
        method="embeddings",
        embeddings_cache_dir=str(tmp_path),
        embeddings_model="all-MiniLM-L6-v2",
    )

    with pytest.raises(
        ConfigError,
        match=re.escape(
            "Offline mode requires a cached embeddings model. Provide --model-path or set conflict.embeddings_model_path."
        ),
    ):
        compute_similarity(
            new_skill,
            FIXTURES,
            config,
            offline=True,
        )



def test_conflict_embeddings_offline_uses_model_path(monkeypatch, tmp_path, capsys) -> None:
    fake_model = _install_fake_sentence_transformers(monkeypatch)
    new_skill = parse_skill(FIXTURES / "conflicting-skill")

    local_model = tmp_path / "local-model"
    local_model.mkdir()

    config = ConflictConfig(
        method="embeddings",
        embeddings_cache_dir=str(tmp_path),
    )

    result = compute_similarity(
        new_skill,
        FIXTURES,
        config,
        embeddings_model_path=str(local_model),
        offline=True,
    )

    assert result.high_conflicts >= 1
    assert fake_model.last_init["model_name"] == str(local_model)
    assert "Downloading model" not in capsys.readouterr().err



def test_conflict_llm_not_implemented() -> None:
    new_skill = parse_skill(FIXTURES / "valid-skill")
    with pytest.raises(
        ConfigError,
        match=re.escape(
            "LLM conflict detection is not yet implemented. Use method: tfidf (default)."
        ),
    ):
        compute_similarity(new_skill, FIXTURES, ConflictConfig(method="llm"))
