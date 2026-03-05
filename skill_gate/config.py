"""
Config loader for skill-gate.yaml.
Supports ${ENV_VAR} expansion in all string values.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from ruamel.yaml import YAML

from skill_gate.models import ConfigError

# ---------------------------------------------------------------------------
# Config sub-models
# ---------------------------------------------------------------------------

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand ${VAR} patterns in strings."""
    if isinstance(value, str):

        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            env_val = os.environ.get(var_name)
            if env_val is None:
                raise ConfigError(
                    f"Environment variable '{var_name}' is referenced in config but not set.\n"
                    f"  → Set it with: export {var_name}=<value>"
                )
            return env_val

        return _ENV_VAR_PATTERN.sub(_replace, value)
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


class AllowListEntry(BaseModel):
    id: str
    reason: str
    file: str | None = None


class ValidateConfig(BaseModel):
    min_description_length: int = 20
    max_description_length: int = 500
    max_body_lines: int = 500
    require_trigger_hint: bool = True
    require_author_in_metadata: bool = True
    require_version_in_metadata: bool = True
    require_evals: bool = False
    vague_phrases: list[str] = Field(default_factory=list)


class SecureConfig(BaseModel):
    block_on: list[str] = Field(default_factory=lambda: ["critical", "high"])
    allow_external_urls_in_scripts: bool = False
    use_snyk_scan: bool = False
    allow_list: list[AllowListEntry] = Field(default_factory=list)


class ConflictConfig(BaseModel):
    similarity_threshold: float = 0.70
    method: Literal["tfidf", "embeddings", "llm"] = "tfidf"
    block_on_high_overlap: bool = True
    high_overlap_threshold: float = 0.75
    medium_overlap_threshold: float = 0.55
    llm_model: str | None = None


class InjectionConfig(BaseModel):
    method: Literal["directory_copy", "git_push", "custom_hook"] = "custom_hook"
    pre_test_hook: str | None = None
    post_test_hook: str | None = None


class TestConfig(BaseModel):
    endpoint: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout_seconds: int = 30
    reload_command: str | None = None
    reload_wait_seconds: int = 10
    reload_health_check_path: str = "/health"
    reload_timeout_seconds: int = 60
    injection: InjectionConfig = Field(default_factory=InjectionConfig)


class NotifyConfig(BaseModel):
    slack_webhook: str | None = None
    github_issues: bool = False
    github_token: str | None = None
    github_repo: str | None = None


class MonitorConfig(BaseModel):
    stale_threshold_days: int = 180
    degrade_after_days: int = 7
    deprecate_after_days: int = 30
    check_ownership: bool = True
    ownership_files: list[str] = Field(default_factory=lambda: ["CODEOWNERS", "MAINTAINERS"])
    ownership_fallback: Literal["warn", "skip"] = "warn"
    notify: NotifyConfig = Field(default_factory=NotifyConfig)


class CIConfig(BaseModel):
    fail_on_warning: bool = False
    post_pr_comment: bool = True
    output_format: Literal["text", "json", "markdown"] = "markdown"


class SkillGateConfig(BaseModel):
    skills_dir: str = "./skills/"
    catalog_path: str = "./skill-catalog.yaml"
    validate: ValidateConfig = Field(default_factory=ValidateConfig)
    secure: SecureConfig = Field(default_factory=SecureConfig)
    conflict: ConflictConfig = Field(default_factory=ConflictConfig)
    test: TestConfig = Field(default_factory=TestConfig)
    monitor: MonitorConfig = Field(default_factory=MonitorConfig)
    ci: CIConfig = Field(default_factory=CIConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG_NAMES = ["skill-gate.yaml", "skill-gate.yml", ".skill-gate.yaml"]


def load_config(path: Path | None = None) -> SkillGateConfig:
    """
    Load and validate skill-gate.yaml.

    Args:
        path: Explicit path to config file. If None, searches for default names
              in the current working directory.

    Returns:
        Validated SkillGateConfig instance.

    Raises:
        ConfigError: If the config file is not found, YAML is invalid,
                     or a referenced environment variable is not set.
    """
    config_path = _resolve_config_path(path)

    if config_path is None:
        # No config file — return defaults
        return SkillGateConfig()

    # Read raw YAML
    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        with open(config_path) as f:
            raw = yaml.load(f)
    except Exception as e:
        raise ConfigError(
            f"Failed to parse config file '{config_path}': {e}\n"
            f"  → Check for YAML syntax errors (invalid indentation, missing quotes, etc.)"
        ) from e

    if raw is None:
        # Empty config file — use defaults
        return SkillGateConfig()

    # Convert ruamel CommentedMap to plain dict
    raw_dict = _to_plain_dict(raw)

    # Expand environment variables
    try:
        expanded = _expand_env_vars(raw_dict)
    except ConfigError:
        raise

    # Validate with Pydantic
    try:
        return SkillGateConfig.model_validate(expanded)
    except Exception as e:
        raise ConfigError(
            f"Invalid config in '{config_path}': {e}\n"
            f"  → Run 'skill-gate init' to see the full config template"
        ) from e


def _resolve_config_path(path: Path | None) -> Path | None:
    """Resolve the config file path."""
    if path is not None:
        if not path.exists():
            raise ConfigError(
                f"Config file not found: '{path}'\n"
                f"  → Run 'skill-gate init' to create a config file"
            )
        return path

    cwd = Path.cwd()
    for name in _DEFAULT_CONFIG_NAMES:
        candidate = cwd / name
        if candidate.exists():
            return candidate

    return None  # No config file found — use defaults


def _to_plain_dict(obj: Any) -> Any:
    """Convert ruamel.yaml CommentedMap/CommentedSeq to plain Python dicts/lists."""
    if hasattr(obj, "items"):
        return {k: _to_plain_dict(v) for k, v in obj.items()}
    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        return [_to_plain_dict(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Config template for `skill-gate init`
# ---------------------------------------------------------------------------

CONFIG_TEMPLATE = """\
# skill-gate.yaml — Configuration for skill-gate
# Run 'skill-gate init' to regenerate this file.
# All string values support ${ENV_VAR} expansion.
#
# Full reference: https://github.com/vaibhavtupe/skill-gate/docs/configuration-reference.md

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
skills_dir: ./skills/
catalog_path: ./skill-catalog.yaml

# ─────────────────────────────────────────────
# Validation rules (skill-gate validate)
# ─────────────────────────────────────────────
validate:
  min_description_length: 20       # Minimum chars in description
  max_description_length: 500      # Maximum chars in description
  max_body_lines: 500              # Max lines in SKILL.md body
  require_trigger_hint: true       # Description must contain "Use when"
  require_author_in_metadata: true
  require_version_in_metadata: true
  require_evals: false             # Set true to block PRs with no evals/
  # vague_phrases:                 # Additional phrases to flag as generic
  #   - "a useful skill"

# ─────────────────────────────────────────────
# Security rules (skill-gate secure)
# ─────────────────────────────────────────────
secure:
  block_on: [critical, high]       # Severities that cause a blocking failure
  allow_external_urls_in_scripts: false
  use_snyk_scan: false             # Requires snyk CLI (future feature)
  # allow_list:                    # Suppress specific findings
  #   - id: EXEC-001
  #     reason: "Standard install pattern"
  #     file: scripts/setup.sh

# ─────────────────────────────────────────────
# Conflict detection (skill-gate conflict)
# ─────────────────────────────────────────────
conflict:
  method: tfidf                    # tfidf | embeddings | llm
  high_overlap_threshold: 0.75    # >= this = HIGH conflict
  medium_overlap_threshold: 0.55  # >= this = MEDIUM conflict
  block_on_high_overlap: true

# ─────────────────────────────────────────────
# Integration testing (skill-gate test) — Phase 2
# ─────────────────────────────────────────────
# test:
#   endpoint: ${AGENT_API_ENDPOINT}
#   api_key: ${AGENT_API_KEY}
#   model: your-agent-model
#   timeout_seconds: 30
#   reload_command: "curl -X POST ${AGENT_ADMIN_URL}/reload"
#   reload_wait_seconds: 10
#   injection:
#     method: custom_hook
#     pre_test_hook: ./hooks/deploy-skill.sh
#     post_test_hook: ./hooks/remove-skill.sh

# ─────────────────────────────────────────────
# Monitoring — Phase 3
# ─────────────────────────────────────────────
# monitor:
#   stale_threshold_days: 180
#   degrade_after_days: 7
#   deprecate_after_days: 30
#   notify:
#     slack_webhook: ${SLACK_WEBHOOK_URL}

# ─────────────────────────────────────────────
# CI/CD
# ─────────────────────────────────────────────
ci:
  fail_on_warning: false
  post_pr_comment: true
  output_format: markdown
"""
