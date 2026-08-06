# Configuration Reference

`skill-guard.yaml` controls all behavior. All string values support `${ENV_VAR}` expansion.

## Example

```yaml
skills_dir: ./skills/

validate:
  min_description_length: 20
  max_description_length: 1024
  max_body_lines: 500
  require_trigger_hint: true
  require_author_in_metadata: false
  require_version_in_metadata: false
  require_evals: false
  anthropic_spec: true
  vague_phrases:
    - "a useful skill"

secure:
  block_on: [critical, high]
  allow_external_urls_in_scripts: false
  skip_references: false
  allow_list:
    - id: EXEC-001
      reason: "Standard install pattern"
      file: scripts/setup.sh

conflict:
  similarity_threshold: 0.70  # legacy; unused — see conflict.* below
  method: tfidf
  high_overlap_threshold: 0.75
  medium_overlap_threshold: 0.55
  block_on_high_overlap: true
  embeddings_cache_dir: .skill-guard-cache/embeddings
  embeddings_model: all-MiniLM-L6-v2
  embeddings_model_path: /path/to/local/model

ci:
  fail_on_warning: false
  output_format: markdown
```

## Fields

### `skills_dir` (string)
Root directory containing skills. Default: `./skills/`

### `validate.*`
- `min_description_length` (int, default 20)
- `max_description_length` (int, default 1024)
- `max_body_lines` (int, default 500)
- `require_trigger_hint` (bool, default true)
- `require_author_in_metadata` (bool, default false) informational (warning-severity) by default; set to true to make missing author metadata a blocker
- `require_version_in_metadata` (bool, default false) informational (warning-severity) by default; set to true to make missing version metadata a blocker
- `require_evals` (bool, default false)
- `anthropic_spec` (bool, default true)
- `vague_phrases` (list[str]) additional phrases to flag

### `secure.*`
- `block_on` (list[str]) severities that cause failure (critical/high/medium/low)
- `allow_external_urls_in_scripts` (bool)
- `skip_references` (bool) skip scanning references/ files for injection patterns
- `allow_list` (list) suppress specific findings

### `conflict.*`
- `similarity_threshold` (float, default `0.70`) legacy field retained for schema compatibility; not read by the conflict engine — `medium_overlap_threshold`/`high_overlap_threshold` and the CLI `--threshold` flag drive actual scoring
- `method` (`tfidf`|`embeddings`|`llm`)
- `high_overlap_threshold` (float)
- `medium_overlap_threshold` (float)
- `block_on_high_overlap` (bool)
- `embeddings_cache_dir` (string, default `.skill-guard-cache/embeddings`)
- `embeddings_model` (string, default `all-MiniLM-L6-v2`)
- `embeddings_model_path` (string, optional) local model path for offline/air-gapped runs

**Tuning tip:** Calibrate thresholds by running `skill-guard conflict` against known similar and dissimilar skills, then adjust `medium_overlap_threshold`/`high_overlap_threshold` (or use `--threshold` for a one-off run).

### `ci.*`
- `fail_on_warning` (bool)
- `output_format` (text|json|markdown)

## Environment Variables

Use `${VAR_NAME}` in any string value. Example:

```yaml
skills_dir: ${SKILLS_DIR}
```

If the environment variable is not set, skill-guard raises a `ConfigError`.
