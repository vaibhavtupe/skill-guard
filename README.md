# skill-gate

**The quality gate for Agent Skills.**

[![PyPI version](https://badge.fury.io/py/skill-gate.svg)](https://badge.fury.io/py/skill-gate)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

skill-gate is a CLI tool that validates, secures, and governs [Agent Skills](https://agentskills.io) across their full lifecycle — from contribution to production monitoring.

## The Problem

Agent Skills are powerful. They're also ungoverned. As soon as more than one person contributes skills to a shared agent, things break in hard-to-diagnose ways:

- A new skill's description overlaps with an existing one → agent picks the wrong skill half the time
- Skills with dangerous scripts get merged because nobody reviewed the `scripts/` directory
- Nobody knows what skills are installed, who owns them, or whether they still work
- A skill passes every test in isolation but fails when the real agent uses it with 25 other skills loaded

skill-gate is the quality gate that catches these problems before they reach production.

## What It Does

```
ONBOARDING (pre-merge, in CI):
  skill-gate validate   → format compliance + quality scoring
  skill-gate secure     → scan for dangerous patterns  
  skill-gate conflict   → detect trigger overlap with existing skills
  skill-gate test       → inject into staging agent, run evals
  skill-gate check      → run all four as a single gate

ONGOING (post-merge, scheduled):
  skill-gate monitor    → re-run evals, detect drift, manage lifecycle
  skill-gate catalog    → searchable registry of approved skills
```

## Quick Start

```bash
pip install skill-gate

# Initialize in your skills repo
skill-gate init

# Validate a skill
skill-gate validate ./skills/my-skill/

# Check for security issues
skill-gate secure ./skills/my-skill/

# Check for conflicts with existing skills
skill-gate conflict ./skills/my-skill/ --against ./skills/

# Run the full gate (validate + secure + conflict)
skill-gate check ./skills/my-skill/ --against ./skills/
```

## Installation

```bash
# Core (static analysis — no agent required)
pip install skill-gate

# With embedding-based conflict detection
pip install skill-gate[embeddings]
```

Requires Python 3.11+.

## Documentation

- [Getting Started](docs/getting-started.md)
- [End-to-End Integration Guide](docs/integration-guide.md) ← start here for real agent setup
- [Writing Evals](docs/eval-authoring-guide.md)
- [Hook Scripts](docs/hooks-guide.md)
- [CI/CD Integration](docs/ci-integration.md)
- [Configuration Reference](docs/configuration-reference.md)

## What skill-gate Does NOT Do

- Does **not** replace [Anthropic's skill-creator](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) for writing skills
- Does **not** host or serve skills — skills live in your repo
- Does **not** modify skills — it reports issues, authors fix them
- Does **not** require a database or server — the catalog is a YAML file in your repo

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). We welcome contributions of all kinds.

## License

Apache 2.0. See [LICENSE](LICENSE).
