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
