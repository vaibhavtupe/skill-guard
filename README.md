# skill-guard

**The quality gate for Agent Skills.**

[![PyPI version](https://badge.fury.io/py/skill-guard.svg)](https://badge.fury.io/py/skill-guard)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

skill-guard is a CLI tool that validates, secures, and governs [Agent Skills](https://agentskills.io) across their full lifecycle — from contribution to production monitoring.

## The Problem

Agent Skills are powerful. They're also ungoverned. As soon as more than one person contributes skills to a shared agent, things break in hard-to-diagnose ways:

- A new skill's description overlaps with an existing one → agent picks the wrong skill half the time
- Skills with dangerous scripts get merged because nobody reviewed the `scripts/` directory
- Nobody knows what skills are installed, who owns them, or whether they still work
- A skill passes every test in isolation but fails when the real agent uses it with 25 other skills loaded

skill-guard is the quality gate that catches these problems before they reach production.

## What It Does

```
ONBOARDING (pre-merge, in CI):
  skill-guard validate   → format compliance + quality scoring
  skill-guard secure     → scan for dangerous patterns  
  skill-guard conflict   → detect trigger overlap with existing skills
  skill-guard test       → runs evals against an OpenAI-compatible endpoint. Supports injection methods: custom_hook (pre/post scripts), directory_copy, and git_push.
  skill-guard check      → runs validate + secure + conflict as a single gate. Agent evals run if --endpoint is configured.

ONGOING (post-merge, scheduled):
  skill-guard monitor    → re-run evals, detect drift, manage lifecycle. Run via cron or CI for continuous drift detection. No built-in scheduler.
  skill-guard catalog    → searchable registry of registered skills (approval workflow planned for v0.7)
```

## Quick Start

```bash
pip install skill-guard

# Initialize in your skills repo
skill-guard init

# Validate a skill
skill-guard validate ./skills/my-skill/

# Check for security issues
skill-guard secure ./skills/my-skill/

# Skip scanning references/ for injection patterns
skill-guard secure ./skills/my-skill/ --skip-references

# Check for conflicts with existing skills
skill-guard conflict ./skills/my-skill/ --against ./skills/

# Run the full gate (validate + secure + conflict; test runs if --endpoint is configured)
skill-guard check ./skills/my-skill/ --against ./skills/
```

### Test injection methods

```yaml
# skill-guard.yaml

test:
  endpoint: http://localhost:8000
  model: gpt-4.1
  injection:
    method: directory_copy
    directory_copy_dir: /app/skills

# Or push into a repo that your agent pulls from:
# test:
#   endpoint: http://localhost:8000
#   model: gpt-4.1
#   injection:
#     method: git_push
#     git_repo_path: /path/to/agent-repo
#     git_remote: origin
#     git_branch: main
#     git_skills_dir: skills
```

### Example Output

```
$ skill-guard validate ./skills/my-skill/

 skill-guard validate — my-skill
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check                     ┃ Result                                           ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ skill_md_exists           │ ✅ SKILL.md found                                │
│ valid_yaml_frontmatter    │ ✅ Valid YAML frontmatter                        │
│ name_field_present        │ ✅ name: my-skill                                │
│ description_field_present │ ✅ description field present                     │
│ directory_name_matches    │ ✅ Directory name matches skill name             │
│ description_trigger_hint  │ ✅ Description contains trigger hint ('Use when')│
│ no_broken_body_paths      │ ✅ No broken relative paths in SKILL.md body     │
│ evals_directory_exists    │ ⚠️ No evals/ directory found                     │
│                           │ → Create evals/config.yaml with test cases       │
│ metadata_has_author       │ ✅ author: my-team                               │
│ metadata_has_version      │ ✅ version: 1.0                                  │
└───────────────────────────┴──────────────────────────────────────────────────┘
Score: 97/100 | Grade: A | Blockers: 0 | Warnings: 1
```

## Installation

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Required. 3.12 and 3.13 tested. |
| pip | any recent | Bundled with Python |
| typer | ≥0.13.0 | Installed automatically |
| Agent endpoint | — | Required only for `skill-guard test` (OpenAI-compatible API) |

> **Note:** `skill-guard validate`, `secure`, `conflict`, `init`, `catalog`, and `check` work fully offline — no agent or API key needed.

## Installation

```bash
# Core (static analysis — no agent required)
pip install skill-guard

# Optional embeddings support
pip install skill-guard[embeddings]

# Optional LLM-based conflict detection
pip install skill-guard[llm]
```

## Conflict Detection Modes

```bash
# TF-IDF (default)
skill-guard conflict ./skills/my-skill/ --against ./skills/ --method tfidf

# Embeddings-based overlap detection
skill-guard conflict ./skills/my-skill/ --against ./skills/ --method embeddings

# Choose a different embeddings model
skill-guard conflict ./skills/my-skill/ --against ./skills/ --method embeddings --model all-MiniLM-L12-v2

# Offline embeddings (local model only; no downloads)
skill-guard conflict ./skills/my-skill/ --against ./skills/ --method embeddings \
  --model-path /models/all-MiniLM-L6-v2 --offline

# LLM-based overlap detection
export OPENAI_API_KEY=...
skill-guard conflict ./skills/my-skill/ --against ./skills/ --method llm
```

`embeddings` uses the `all-MiniLM-L6-v2` sentence-transformers model by default (override with `--model`, `--model-path`, or `conflict.embeddings_model`/`conflict.embeddings_model_path`) and caches downloads under `conflict.embeddings_cache_dir` (default `.skill-guard-cache/embeddings/`). On first download, it prints a "Downloading model..." message to stderr. Use `--offline` to require a local/cached model and skip downloads. `llm` uses the OpenAI Chat API with `gpt-4o-mini` by default.

### Ignoring known conflicts

Add `conflict_ignore` to your SKILL.md frontmatter to skip comparisons against specific skills:

```yaml
---
name: my-skill
description: "Use when ..."
conflict_ignore:
  - legacy-skill
  - skills/legacy-skill/SKILL.md
---
```

## Documentation

- [Getting Started](docs/getting-started.md)
- [End-to-End Integration Guide](docs/integration-guide.md) ← start here for real agent setup
- [Writing Evals](docs/eval-authoring-guide.md)
- [Hook Scripts](docs/hooks-guide.md)
- [CI/CD Integration](docs/ci-integration.md)
- [Configuration Reference](docs/configuration-reference.md)
- [Automation Policy](docs/automation-policy.md)
- [Release Gate Checklist](docs/release-gate.md)
- [Roadmap](ROADMAP.md)

## Anthropic Spec Validation

`skill-guard validate` includes Anthropic AgentSkills spec compliance checks by default. Set `validate.anthropic_spec: false` in `skill-guard.yaml` if you need to disable those additional findings.

## Exit Codes

- `0`: success
- `1`: validation/security failures
- `2`: warnings only (when `fail_on_warning` is false)
- `3`: config error
- `4`: parse error
- `5`: hook script failure
- `6`: health check timeout

## Pre-commit

Use `pre-commit` to enforce checks before skill changes land:

```yaml
repos:
  - repo: https://github.com/vaibhavtupe/skill-guard
    rev: v0.6.0
    hooks:
      - id: skill-guard-validate
      - id: skill-guard-secure
      - id: skill-guard-check
```

These hooks run against changed `SKILL.md` files, deduplicate by skill root, and then execute the corresponding `skill-guard` command for each affected skill.

## Templates

Use `skill-guard init --template base` to scaffold a new skill, or `skill-guard init --list-templates` to see the available scaffolds. Generated templates include `SKILL.md`, `evals/`, `references/`, `scripts/`, and `assets/` so they validate immediately.

## GitHub Actions

```yaml
name: skill-guard PR Gate

on:
  pull_request:
    paths:
      - "skills/**"

jobs:
  skill-guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install skill-guard
      - run: |
          skill-guard check skills/ \
            --changed \
            --base-ref "${{ github.event.pull_request.base.sha }}" \
            --head-ref "${{ github.sha }}" \
            --format md > skill-guard-summary.md
```

See [docs/ci-integration.md](docs/ci-integration.md) for the canonical workflow, JSON + markdown artifact strategy, and the checked-in example at [.github/workflows/skill-guard-pr-gate.yml](.github/workflows/skill-guard-pr-gate.yml).

## What skill-guard Does NOT Do

- Does **not** replace [Anthropic's skill-creator](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) for writing skills
- Does **not** host or serve skills — skills live in your repo
- Does **not** modify skills — it reports issues, authors fix them
- Does **not** require a database or server — the catalog is a YAML file in your repo

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). We welcome contributions of all kinds.

For planning and release discipline:
- `ROADMAP.md` is the canonical scope source
- `docs/automation-policy.md` defines PM ↔ Dev workflow
- `docs/release-gate.md` is the required pre-release checklist

## License

Apache 2.0. See [LICENSE](LICENSE).
