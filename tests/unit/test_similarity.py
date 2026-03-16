import re
from pathlib import Path

import pytest

from skill_guard.config import ConflictConfig
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
    # Should not conflict with itself
    assert all(m.existing_skill_name != "valid-skill" for m in result.matches)


@pytest.mark.parametrize(
    ("method", "message"),
    [
        (
            "embeddings",
            "Embeddings conflict detection is not yet implemented. Use method: tfidf (default).",
        ),
        (
            "llm",
            "LLM conflict detection is not yet implemented. Use method: tfidf (default).",
        ),
    ],
)
def test_conflict_unsupported_method_raises_config_error(method: str, message: str) -> None:
    new_skill = parse_skill(FIXTURES / "valid-skill")

    with pytest.raises(ConfigError, match=re.escape(message)):
        compute_similarity(new_skill, FIXTURES, ConflictConfig(method=method))
