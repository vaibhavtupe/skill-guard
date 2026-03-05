# CI Integration Guide

This guide covers integrating `skill-gate` into your CI/CD pipeline for automated skill quality enforcement, security scanning, conflict detection, and agent eval testing.

---

## Overview

`skill-gate` exposes four composable commands you can chain in CI:

| Command | What it checks |
|---|---|
| `skill-gate validate` | Schema, required fields, description quality, eval presence |
| `skill-gate secure` | Prompt injection patterns, scope violations, banned phrases |
| `skill-gate conflict` | Semantic overlap with existing skills (TF-IDF cosine similarity) |
| `skill-gate test` | Live evals against your agent via the OpenAI Responses API |
| `skill-gate check` | Runs validate → secure → conflict → test in one pass |

---

## Quickstart: GitHub Actions

### Minimal CI workflow (validate + secure + conflict)

```yaml
# .github/workflows/skill-gate-ci.yml
name: skill-gate CI

on:
  pull_request:
    paths:
      - 'skills/**'

jobs:
  skill-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install skill-gate
        run: pip install agentskill-gate

      - name: Validate skill
        run: skill-gate validate skills/my-skill --format json

      - name: Security scan
        run: skill-gate secure skills/my-skill --format json

      - name: Conflict check
        run: skill-gate conflict skills/my-skill --against skills/ --format json
```

### Full pipeline with agent eval testing

```yaml
name: skill-gate Full CI

on:
  pull_request:
    paths:
      - 'skills/**'

jobs:
  skill-gate:
    runs-on: ubuntu-latest
    env:
      AGENT_ENDPOINT: ${{ secrets.AGENT_ENDPOINT }}
      AGENT_API_KEY: ${{ secrets.AGENT_API_KEY }}

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install skill-gate
        run: pip install agentskill-gate

      # Run the full pipeline in one command
      - name: skill-gate check
        run: |
          skill-gate check skills/my-skill \
            --against skills/ \
            --endpoint $AGENT_ENDPOINT \
            --format json
```

Exit codes from `skill-gate check`:
- `0` — all checks passed
- `1` — a blocking check failed (validation, security, or conflict)
- `2` — blocking checks passed but warnings present
- `3` — config error
- `4` — skill parse error

---

## Running `skill-gate test` in CI

`skill-gate test` sends eval prompts from your skill's `evals/` directory to your agent and validates the responses.

### Prerequisites

1. Your skill must have an `evals/` directory with `config.yaml` and prompt files:

```
my-skill/
├── SKILL.md
└── evals/
    ├── config.yaml
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

### Running the eval

```bash
skill-gate test skills/my-skill \
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
skill-gate catalog register skills/my-skill --catalog skill-catalog.yaml

# Use catalog in CI (fast, no filesystem scan of all skills)
skill-gate conflict skills/pr-skill --against skill-catalog.yaml
```

### Maintaining the catalog in CI

```yaml
- name: Update catalog on merge
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
  run: |
    skill-gate catalog register skills/my-skill --catalog skill-catalog.yaml
    git add skill-catalog.yaml
    git commit -m "chore: update skill catalog" || true
    git push
```

---

## Output formats

All commands support `--format text|json|md`. Use `json` in CI for structured parsing, `md` for PR comment annotations.

### Posting results as a PR comment (GitHub Actions)

```yaml
- name: Run skill-gate check (JSON)
  id: sg
  run: |
    skill-gate check skills/my-skill --against skills/ --format md > sg-report.md
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
# skill-gate.yaml
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

See [configuration-reference.md](configuration-reference.md) for all `skill-gate.yaml` options.

---

## Versioning

| Version | Phase | Key additions |
|---|---|---|
| `0.1.x` | Phase 1 | `validate`, `secure`, `conflict`, `init` |
| `0.2.x` | Phase 2 | `test`, `catalog`, `check`, integration testing, this guide |
| `0.3.x` | Phase 3 | `monitor`, Slack/GitHub notifications, auto-stage transitions |
