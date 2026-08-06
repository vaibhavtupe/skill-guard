from pathlib import Path

import pytest

from skill_guard.config import ValidateConfig, load_config
from skill_guard.models import ConfigError


def test_load_config_defaults(tmp_path: Path):
    cwd = Path.cwd()
    try:
        # change to empty dir, no config
        import os

        os.chdir(tmp_path)
        cfg = load_config()
        assert cfg.validate.min_description_length == 20
        assert cfg.conflict.embeddings_cache_dir == ".skill-guard-cache/embeddings"
        assert cfg.conflict.embeddings_model == "all-MiniLM-L6-v2"
        assert cfg.conflict.embeddings_model_path is None
    finally:
        os.chdir(cwd)


def test_load_config_missing_file(tmp_path: Path):
    missing = tmp_path / "missing.yaml"
    with pytest.raises(ConfigError):
        load_config(missing)


def test_default_validate_config_does_not_block_on_missing_author_or_version():
    config = ValidateConfig()
    assert config.require_author_in_metadata is False
    assert config.require_version_in_metadata is False
    assert config.max_description_length == 1024


def test_env_var_expansion(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FOO", "bar")
    config_file = tmp_path / "skill-guard.yaml"
    config_file.write_text("""\nskills_dir: ${FOO}\n""", encoding="utf-8")
    cfg = load_config(config_file)
    assert cfg.skills_dir == "bar"


def test_missing_env_var(tmp_path: Path):
    config_file = tmp_path / "skill-guard.yaml"
    config_file.write_text("""\nskills_dir: ${NOT_SET}\n""", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(config_file)


def test_documented_config_fields_load(tmp_path: Path) -> None:
    config_file = tmp_path / "skill-guard.yaml"
    config_file.write_text(
        ("validate:\n  anthropic_spec: false\nconflict:\n  similarity_threshold: 0.82\n"),
        encoding="utf-8",
    )

    cfg = load_config(config_file)

    assert cfg.validate.anthropic_spec is False
    assert cfg.conflict.similarity_threshold == 0.82
