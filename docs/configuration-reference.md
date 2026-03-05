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
  use_snyk_scan: false
  allow_list:
    - id: EXEC-001
      reason: "Standard install pattern"
      file: scripts/setup.sh

conflict:
  method: tfidf
  high_overlap_threshold: 0.75
  medium_overlap_threshold: 0.55
  block_on_high_overlap: true

ci:
  fail_on_warning: false
  post_pr_comment: true
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
- `use_snyk_scan` (bool, Phase 3+)
- `allow_list` (list) suppress specific findings

### `conflict.*`
- `method` (tfidf|embeddings|llm)
- `high_overlap_threshold` (float)
- `medium_overlap_threshold` (float)
- `block_on_high_overlap` (bool)

### `ci.*`
- `fail_on_warning` (bool)
- `post_pr_comment` (bool)
- `output_format` (text|json|markdown)

## Environment Variables

Use `${VAR_NAME}` in any string value. Example:

```yaml
skills_dir: ${SKILLS_DIR}
```

If the environment variable is not set, skill-guard raises a `ConfigError`.
