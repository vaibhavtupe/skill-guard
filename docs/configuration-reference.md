# Configuration Reference

`skill-guard.yaml` controls all behavior. All string values support `${ENV_VAR}` expansion.

## Example

```yaml
skills_dir: ./skills/
catalog_path: ./skill-catalog.yaml

validate:
  min_description_length: 20
  max_description_length: 500
  max_body_lines: 500
  require_trigger_hint: true
  require_author_in_metadata: true
  require_version_in_metadata: true
  require_evals: false
  vague_phrases:
    - "a useful skill"

secure:
  block_on: [critical, high]
  allow_external_urls_in_scripts: false
  skip_references: false
  use_snyk_scan: false  # reserved for future integration
  allow_list:
    - id: EXEC-001
      reason: "Standard install pattern"
      file: scripts/setup.sh

conflict:
  method: tfidf
  high_overlap_threshold: 0.75
  medium_overlap_threshold: 0.55
  block_on_high_overlap: true
  embeddings_cache_dir: .skill-guard-cache/embeddings
  embeddings_model: all-MiniLM-L6-v2
  embeddings_model_path: /path/to/local/model
  llm_model: gpt-4o-mini
  llm_max_concurrent: 5

monitor:
  stale_threshold_days: 180
  degrade_after_failures: 7
  deprecate_after_failures: 30

ci:
  fail_on_warning: false
  post_pr_comment: false  # reserved for future GitHub integration
  output_format: markdown
```

## Fields

### `skills_dir` (string)
Root directory containing skills. Default: `./skills/`

### `catalog_path` (string)
Path to `skill-catalog.yaml`. Default: `./skill-catalog.yaml`

### `validate.*`
- `min_description_length` (int, default 20)
- `max_description_length` (int, default 500)
- `max_body_lines` (int, default 500)
- `require_trigger_hint` (bool, default true)
- `require_author_in_metadata` (bool, default true)
- `require_version_in_metadata` (bool, default true)
- `require_evals` (bool, default false)
- `vague_phrases` (list[str]) additional phrases to flag

### `secure.*`
- `block_on` (list[str]) severities that cause failure (critical/high/medium/low)
- `allow_external_urls_in_scripts` (bool)
- `skip_references` (bool) skip scanning references/ files for injection patterns
- `use_snyk_scan` (bool, reserved for future integration)
- `allow_list` (list) suppress specific findings

### `conflict.*`
- `method` (`tfidf`|`embeddings`|`llm`)
- `high_overlap_threshold` (float)
- `medium_overlap_threshold` (float)
- `block_on_high_overlap` (bool)
- `embeddings_cache_dir` (string, default `.skill-guard-cache/embeddings`)
- `embeddings_model` (string, default `all-MiniLM-L6-v2`)
- `embeddings_model_path` (string, optional) local model path for offline/air-gapped runs
- `llm_model` (string, default `gpt-4o-mini`)
- `llm_max_concurrent` (int, default `5`)

**Tuning tip:** Calibrate thresholds by running `skill-guard conflict` against known similar and dissimilar skills, then adjust `medium_overlap_threshold`/`high_overlap_threshold` (or use `--threshold` for a one-off run).

### `test.*`
- `endpoint` (string) agent endpoint URL
- `api_key` (string, optional)
- `model` (string, optional)
- `timeout_seconds` (int, default 30)
- `workspace_dir` (string, optional) write AgentSkills eval artifacts
- `reload_command` (string, optional)
- `reload_wait_seconds` (int)
- `reload_health_check_path` (string)
- `reload_timeout_seconds` (int)
- `injection.method` (`custom_hook`|`directory_copy`|`git_push`)
- `injection.pre_test_hook` / `injection.post_test_hook` (string, custom hooks)
- `injection.directory_copy_dir` (string, for `directory_copy`)
- `injection.git_repo_path` (string, for `git_push`)
- `injection.git_remote` (string, default `origin`)
- `injection.git_branch` (string, optional)
- `injection.git_skills_dir` (string, default `skills`)
- `injection.git_commit_message` (string, optional)

### `monitor.*`
- `stale_threshold_days` (int)
- `degrade_after_failures` (int; `degrade_after_days` still loads as a deprecated alias)
- `deprecate_after_failures` (int; `deprecate_after_days` still loads as a deprecated alias)
- Run via cron or CI for continuous drift detection. No built-in scheduler.

### `ci.*`
- `fail_on_warning` (bool)
- `post_pr_comment` (bool, reserved for future integration)
- `output_format` (text|json|markdown)

## Environment Variables

Use `${VAR_NAME}` in any string value. Example:

```yaml
skills_dir: ${SKILLS_DIR}
```

If the environment variable is not set, skill-guard raises a `ConfigError`.
