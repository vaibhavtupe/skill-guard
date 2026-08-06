# CI Integration Guide

This guide covers integrating `skill-guard` into your CI/CD pipeline for automated skill quality enforcement, security scanning, and conflict detection.

---

## Overview

`skill-guard` exposes four composable commands you can chain in CI:

| Command | What it checks |
|---|---|
| `skill-guard validate` | Schema, required fields, description quality, eval presence |
| `skill-guard secure` | Prompt injection patterns, scope violations, banned phrases |
| `skill-guard conflict` | Semantic overlap with existing skills (TF-IDF cosine similarity) |
| `skill-guard check` | Runs validate → secure → conflict in one pass |

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
- `2` — warnings only (when `fail_on_warning` is false)
- `3` — config error
- `4` — skill parse error

Warnings remain in the markdown and JSON reports, but the canonical PR gate stays green unless
`ci.fail_on_warning: true` promotes them to failures.

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

If you want PR comments, post `skill-guard-summary.md` from the canonical workflow as-is.
The primary path should not depend on shell glue like `git diff | head -1`; let `check --changed`
resolve the skill set directly from the PR commit range.

---

## Configuration reference

See [configuration-reference.md](configuration-reference.md) for all `skill-guard.yaml` options.

---

## Scope note

This guide covers the shipped CI path in the repo today: the default PR gate around
`skill-guard check --changed`.
