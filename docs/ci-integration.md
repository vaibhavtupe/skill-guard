# CI Integration Guide

This guide covers integrating `skill-guard` into your CI/CD pipeline for automated skill quality enforcement, security scanning, conflict detection, and agent eval testing.

---

## Overview

`skill-guard` exposes four composable commands you can chain in CI:

| Command | What it checks |
|---|---|
| `skill-guard validate` | Schema, required fields, description quality, eval presence |
| `skill-guard secure` | Prompt injection patterns, scope violations, banned phrases |
| `skill-guard conflict` | Semantic overlap with existing skills (TF-IDF cosine similarity) |
| `skill-guard test` | Live evals against your agent via the OpenAI Responses API |
| `skill-guard check` | Runs validate → secure → conflict → test in one pass |

---

## Quickstart: GitHub Actions

### Minimal CI workflow (validate + secure + conflict)

```yaml
# .github/workflows/skill-guard-ci.yml
name: skill-guard CI

on:
  pull_request:
    paths:
      - 'skills/**'

jobs:
  skill-guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install skill-guard
        run: pip install skill-guard

      - name: Validate skill
        run: skill-guard validate skills/my-skill --format json

      - name: Security scan
        run: skill-guard secure skills/my-skill --format json

      - name: Conflict check
        run: skill-guard conflict skills/my-skill --against skills/ --format json
```

### Full pipeline with agent eval testing

```yaml
name: skill-guard Full CI

on:
  pull_request:
    paths:
      - 'skills/**'

jobs:
  skill-guard:
    runs-on: ubuntu-latest
    env:
      AGENT_ENDPOINT: ${{ secrets.AGENT_ENDPOINT }}
      AGENT_API_KEY: ${{ secrets.AGENT_API_KEY }}

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install skill-guard
        run: pip install skill-guard

      # Run the full pipeline in one command
      - name: skill-guard check
        run: |
          skill-guard check skills/my-skill \
            --against skills/ \
            --endpoint $AGENT_ENDPOINT \
            --format json
```

Exit codes from `skill-guard check`:
- `0` — all checks passed
- `1` — a blocking check failed (validation, security, or conflict)
- `2` — blocking checks passed but warnings present
- `3` — config error
- `4` — skill parse error

---

## Running `skill-guard test` in CI

`skill-guard test` sends eval prompts from your skill's `evals/` directory to your agent and validates the responses.

### Prerequisites

1. Your skill must have an `evals/` directory with either `config.yaml` (prompt files) or `evals.json` (inline prompts):

```
my-skill/
├── SKILL.md
└── evals/
    ├── config.yaml
    ├── evals.json
    └── prompts/
        ├── basic.md
        └── edge-case.md
```

2. `evals/config.yaml` format:

```yaml
tests:
  - name: basic-usage
    prompt_file: prompts/basic.md
    expect:
      contains: ["diagnosed", "latency"]
      not_contains: ["I cannot help"]
      max_latency_ms: 3000
      skill_triggered: my-skill   # optional: assert tool call by name

  - name: out-of-scope
    prompt_file: prompts/out-of-scope.md
    expect:
      not_contains: ["traceroute", "packet"]
      skill_not_triggered: my-skill
```

3. `evals/evals.json` format:

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "My AWS connection keeps dropping packets.",
      "expected_output": "diagnosed"
    }
  ]
}
```

`expected_output` records the human-readable success criteria. If you omit `expect` checks, the test is flagged **needs review** (non-blocking).

### Running the eval

```bash
skill-guard test skills/my-skill \
  --endpoint https://your-agent.example.com \
  --api-key $AGENT_API_KEY \
  --model gpt-4.1 \
  --format json
```

The tool posts each prompt to `{endpoint}/v1/responses` using the OpenAI Responses API schema and validates the response against your `expect` block.

### Supported `expect` checks

| Field | Type | Description |
|---|---|---|
| `contains` | `list[str]` | All strings must appear in response text |
| `not_contains` | `list[str]` | None of these strings may appear in response text |
| `min_length` | `int` | Response text must be at least this many characters |
| `max_latency_ms` | `int` | Round-trip latency must not exceed this threshold |
| `skill_triggered` | `str` | A tool call with this name must appear in the response |
| `skill_not_triggered` | `str` | A tool call with this name must NOT appear |

---

## Catalog-based conflict detection

For large repos, scanning a skills directory on every PR is slow. Use a pre-built catalog YAML as the `--against` source instead:

```bash
# Build the catalog once (e.g., on merge to main)
skill-guard catalog register skills/my-skill --catalog skill-catalog.yaml

# Use catalog in CI (fast, no filesystem scan of all skills)
skill-guard conflict skills/pr-skill --against skill-catalog.yaml
```

### Maintaining the catalog in CI

```yaml
- name: Update catalog on merge
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
  run: |
    skill-guard catalog register skills/my-skill --catalog skill-catalog.yaml
    git add skill-catalog.yaml
    git commit -m "chore: update skill catalog" || true
    git push
```

---

## Output formats

All commands support `--format text|json|md`. Use `json` in CI for structured parsing, `md` for PR comment annotations.

### Posting results as a PR comment (GitHub Actions)

```yaml
- name: Run skill-guard check (JSON)
  id: sg
  run: |
    skill-guard check skills/my-skill --against skills/ --format md > sg-report.md
    echo "exit_code=$?" >> $GITHUB_OUTPUT

- name: Comment on PR
  uses: actions/github-script@v7
  with:
    script: |
      const fs = require('fs');
      const body = fs.readFileSync('sg-report.md', 'utf8');
      github.rest.issues.createComment({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: context.issue.number,
        body,
      });
```

---

## Pre/post test hooks

For skills that need agent state setup before evals run (e.g., loading fixtures, resetting DB), use hook scripts:

```yaml
# skill-guard.yaml
test:
  endpoint: https://your-agent.example.com
  injection:
    pre_test_hook: hooks/pre-test.sh
    post_test_hook: hooks/post-test.sh
  reload_timeout_seconds: 10
```

Hook scripts receive two arguments: `<skill_path> <endpoint_url>`. Exit non-zero to abort the test run.

---

## Configuration reference

See [configuration-reference.md](configuration-reference.md) for all `skill-guard.yaml` options.

---

## Versioning

| Version | Phase | Key additions |
|---|---|---|
| `0.1.x` | Phase 1 | `validate`, `secure`, `conflict`, `init` |
| `0.2.x` | Phase 2 | `test`, `catalog`, `check`, integration testing, this guide |
| `0.3.x` | Phase 3 | `monitor`, Slack/GitHub notifications, auto-stage transitions |
