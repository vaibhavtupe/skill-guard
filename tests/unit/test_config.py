from pathlib import Path

import pytest

from skill_guard.config import load_config
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
        assert cfg.conflict.llm_model == "gpt-4o-mini"
        assert cfg.conflict.llm_max_concurrent == 5
    finally:
        os.chdir(cwd)


def test_load_config_missing_file(tmp_path: Path):
    missing = tmp_path / "missing.yaml"
    with pytest.raises(ConfigError):
        load_config(missing)


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


def test_monitor_failure_aliases_load_from_legacy_keys(tmp_path: Path) -> None:
    config_file = tmp_path / "skill-guard.yaml"
    config_file.write_text(
        ("monitor:\n  degrade_after_days: 3\n  deprecate_after_days: 9\n"),
        encoding="utf-8",
    )

    cfg = load_config(config_file)

    assert cfg.monitor.degrade_after_failures == 3
    assert cfg.monitor.deprecate_after_failures == 9


def test_documented_config_fields_load(tmp_path: Path) -> None:
    config_file = tmp_path / "skill-guard.yaml"
    config_file.write_text(
        (
            "validate:\n"
            "  anthropic_spec: false\n"
            "secure:\n"
            "  use_snyk_scan: true\n"
            "conflict:\n"
            "  similarity_threshold: 0.82\n"
            "test:\n"
            "  baseline: true\n"
            "  workspace: ./eval-artifacts\n"
            "monitor:\n"
            "  notify:\n"
            "    github_issues: true\n"
            "    github_token: token\n"
            "    github_repo: owner/repo\n"
            "ci:\n"
            "  post_pr_comment: true\n"
        ),
        encoding="utf-8",
    )

    cfg = load_config(config_file)

    assert cfg.validate.anthropic_spec is False
    assert cfg.secure.use_snyk_scan is True
    assert cfg.conflict.similarity_threshold == 0.82
    assert cfg.test.baseline is True
    assert cfg.test.workspace_dir == "./eval-artifacts"
    assert cfg.monitor.notify.github_issues is True
    assert cfg.monitor.notify.github_token == "token"
    assert cfg.monitor.notify.github_repo == "owner/repo"
    assert cfg.ci.post_pr_comment is True
