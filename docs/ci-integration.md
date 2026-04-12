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

### Canonical PR gate workflow

The recommended PR gate is a single repo-aware `check --changed` run rooted at your skills directory.
It evaluates every changed skill in the PR, writes a markdown summary for humans, writes JSON for machines,
uploads both as artifacts, and fails the workflow only on blocking failures.

This repo includes the canonical example at `.github/workflows/skill-guard-pr-gate.yml`:

```yaml
name: skill-guard PR Gate

on:
  pull_request:
    paths:
      - "skills/**"
      - "skill-guard.yaml"

permissions:
  contents: read

jobs:
  skill-guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install --upgrade pip && python -m pip install skill-guard
      - id: skill_guard
        shell: bash
        run: |
          set +e

          BASE_SHA="${{ github.event.pull_request.base.sha }}"
          HEAD_SHA="${{ github.sha }}"

          skill-guard check skills/ \
            --changed \
            --base-ref "$BASE_SHA" \
            --head-ref "$HEAD_SHA" \
            --format md > skill-guard-summary.md
          md_exit=$?

          skill-guard check skills/ \
            --changed \
            --base-ref "$BASE_SHA" \
            --head-ref "$HEAD_SHA" \
            --format json > skill-guard-report.json
          json_exit=$?

          exit_code=$md_exit
          if [ "$json_exit" -gt "$exit_code" ]; then
            exit_code=$json_exit
          fi

          cat skill-guard-summary.md >> "$GITHUB_STEP_SUMMARY"
          echo "exit_code=$exit_code" >> "$GITHUB_OUTPUT"
          exit 0
      - uses: actions/upload-artifact@v4
        with:
          name: skill-guard-pr-gate
          path: |
            skill-guard-summary.md
            skill-guard-report.json
      - if: steps.skill_guard.outputs.exit_code != '0'
        run: exit 1
```

Exit codes from the PR-gate `skill-guard check --changed` flow:
- `0` — no blocking failures in the changed skills
- `1` — at least one changed skill hit a blocking failure
- `3` — config error
- `4` — skill parse error
- `5` — test hook error
- `6` — agent health/setup error

Warnings remain in the markdown and JSON reports, but the canonical PR gate stays green unless
`ci.fail_on_warning: true` promotes them to failures.

---

## Running `skill-guard test` in CI

`skill-guard test` sends eval prompts from your skill's `evals/` directory to your agent and validates the responses.

For the full eval iteration loop (run → review → revise → expand tests), see [Writing Evals](eval-authoring-guide.md). If you want persistent artifacts for manual review, use `--workspace` as described in [Workspace output](eval-authoring-guide.md#workspace-output-agentskills-eval-artifacts).

Recommended CI path:
- use `test.injection.method: custom_hook`
- use a stable `reload_health_check_path`
- use `--workspace` so every run writes deterministic debug artifacts

`directory_copy` and `git_push` remain supported, but they are secondary paths. They add host or repo state that is harder to keep deterministic in CI.

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

`evals/evals.json` is the canonical format. `config.yaml` remains supported for prompt-file workflows. If both exist, `evals.json` takes precedence; `config.yaml`-only setups may emit an Anthropic-spec warning about missing `evals.json`.

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
  --workspace ./eval-workspace \
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

All commands support `--format text|json|md`.

For the canonical PR gate:
- use `--format md` to produce a concise summary plus per-skill table for `GITHUB_STEP_SUMMARY`
- use `--format json` to persist the full aggregate payload as an artifact for machine parsing

The markdown contract is:
- one run summary with mode, counts, final status, and a concise summary line
- one per-skill table with change type plus validation/security/conflict/test/status columns

The JSON contract is:
- top-level `command` and `timestamp`
- aggregate `result` payload with run counts, final status, summary, and full per-skill detail

The trust-state contract is:
- `clean`: no action required
- `warning`: non-blocking issue
- `exception`: intentional exception or suppression is present
- `needs_review`: human review required even though no blocking failure occurred
- `blocking`: merge-stopping problem

For `check`, keep distinguishing CI-facing `status` from semantic `trust_state`:
- `status` drives pass/warning/fail behavior in CI
- `trust_state` explains what kind of attention the finding needs

If you want PR comments, post `skill-guard-summary.md` from the canonical workflow as-is.
The primary path should not depend on shell glue like `git diff | head -1`; let `check --changed`
resolve the skill set directly from the PR commit range.

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

This is the recommended CI injection path. Keep the hook idempotent, pair it with a health endpoint, and rely on workspace artifacts for failed-run diagnosis.

---

## Configuration reference

See [configuration-reference.md](configuration-reference.md) for all `skill-guard.yaml` options.

---

## Scope note

This guide covers the shipped CI paths in the repo today:
- the default PR gate around `skill-guard check --changed`
- optional live eval runs with `skill-guard test`

Monitoring and notification workflows exist in the CLI, but they are not part of the default v0.8 PR-gate path.
