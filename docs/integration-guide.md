# End-to-End Integration Guide

How to integrate skill-guard into an existing skills repo and test against a real OpenAI Responses API-compatible agent.

---

## Overview

```
Your skills repo
├── skills/
│   ├── my-skill/
│   │   ├── SKILL.md
│   │   └── evals/
│   ├── another-skill/
│   └── skill-catalog.yaml     ← managed by skill-guard catalog
├── skill-guard.yaml            ← skill-guard config
└── .github/workflows/
    ├── skill-guard-ci.yml      ← PR gate (validate+secure+conflict; test if endpoint configured)
    └── skill-guard-monitor.yml ← weekly health check for continuous drift detection
```

---

## Step 1: Initialize skill-guard in your repo

```bash
pip install skill-guard
cd your-skills-repo
skill-guard init
```

This creates `skill-guard.yaml` with commented defaults. Edit it:

```yaml
# skill-guard.yaml
skills_dir: ./skills/
catalog_path: ./skill-catalog.yaml

validate:
  require_evals: true          # block if no evals/ directory

test:
  endpoint: ${AGENT_API_ENDPOINT}   # your agent's base URL
  api_key: ${AGENT_API_KEY}
  model: gpt-4.1                    # model your agent uses
  reload_timeout_seconds: 30

monitor:
  stale_threshold_days: 180
  degrade_after_failures: 7
  notify:
    slack_webhook: ${SLACK_WEBHOOK_URL}   # optional
```

---

## Step 2: Add evals to your skills

Each skill needs an `evals/` directory for `skill-guard test` to work. See [Writing Evals](eval-authoring-guide.md) for the eval authoring + iteration loop (including workspace artifacts), and [CI Integration](ci-integration.md) for running the same loop in GitHub Actions.

Minimum structure (choose one format):

```
skills/my-skill/
├── SKILL.md
└── evals/
    ├── config.yaml         # YAML format
    ├── evals.json           # JSON format (inline prompts)
    └── prompts/
        ├── basic.md        # positive test — skill should trigger
        └── out-of-scope.md # negative test — skill should NOT trigger
```

`evals/evals.json` is the canonical format. `config.yaml` remains supported for prompt-file workflows. If both exist, `evals.json` takes precedence; `config.yaml`-only setups may emit an Anthropic-spec warning about missing `evals.json`.

`evals/config.yaml`:
```yaml
tests:
  - name: basic-usage
    prompt_file: prompts/basic.md
    expect:
      contains: ["diagnosed"]
      skill_triggered: my-skill

  - name: out-of-scope
    prompt_file: prompts/out-of-scope.md
    expect:
      skill_not_triggered: my-skill
```

`evals/evals.json`:
```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "My AWS connection keeps dropping packets. Can you help diagnose?",
      "expected_output": "diagnosed"
    }
  ]
}
```

`expected_output` captures the human-readable success criteria. If you don't include explicit `expect` checks, the test is marked **needs review** (non-blocking).

---

## Step 3: What your agent needs to expose

skill-guard communicates with your agent via the **OpenAI Responses API** format. Your agent needs two endpoints:

### `GET /health` → 200 OK
```json
{"status": "ok"}
```
Used to confirm the agent is ready after skill injection.

### `POST /v1/responses`
Request format (OpenAI Responses API):
```json
{
  "model": "gpt-4.1",
  "input": "My AWS connection keeps dropping packets. Can you help diagnose?"
}
```

Response format skill-guard parses:
```json
{
  "output": [
    {
      "type": "tool_call",
      "name": "my-skill"
    },
    {
      "type": "message",
      "content": [
        {
          "type": "output_text",
          "text": "I'll help diagnose the connectivity issue..."
        }
      ]
    }
  ]
}
```

skill-guard extracts:
- **Tool calls** from `output[].type == "tool_call"` → `output[].name`
- **Response text** from `output[].type == "message"` → `output[].content[].text`

Any OpenAI-compatible agent (OpenAI Assistants, custom FastAPI wrapper, LangChain agent with Responses API adapter) works as-is.

---

## Step 4: Run locally first

```bash
# Export your agent config
export AGENT_API_ENDPOINT=http://localhost:8000
export AGENT_API_KEY=your-key   # omit if no auth

# 1. Run the default gate
skill-guard check skills/my-skill/ --against skills/

# 2. Optional: run evals against your agent
skill-guard test skills/my-skill/ \
  --endpoint $AGENT_API_ENDPOINT \
  --api-key $AGENT_API_KEY \
  --model gpt-4.1

# 3. Optional: run the gate plus live evals in one command
skill-guard check skills/my-skill/ \
  --against skills/ \
  --endpoint $AGENT_API_ENDPOINT
```

`skill-guard check` is the default pre-merge workflow. Reach for `validate`, `secure`, or `conflict` directly only when you want to inspect one stage in isolation.

`skill-guard test` runs evals against an OpenAI-compatible endpoint. Use `pre_test_hook`/`post_test_hook` for your own deploy/teardown flow.

`skill-guard check` runs validate + secure + conflict as a single gate. Agent evals run if `--endpoint` is configured.

All commands are scriptable in CI; see the README for exit codes.

---

## Step 5: Advanced / Optional Catalog Workflow

After a skill passes all checks, register it:

```bash
skill-guard catalog register skills/my-skill/ --catalog skill-catalog.yaml
```

This creates/updates `skill-catalog.yaml` with the skill's metadata, quality score, and stage (`staging` by default).

```bash
# View catalog
skill-guard catalog list

# Promote to production (manual, after your review process)
# Edit skill-catalog.yaml: change stage: staging → stage: production
```

Commit `skill-catalog.yaml` to your repo — it's the source of truth for deployed skills.

---

## Step 6: Set up CI (GitHub Actions)

Create `.github/workflows/skill-guard-ci.yml`:

```yaml
name: skill-guard CI

on:
  pull_request:
    paths:
      - 'skills/**'

jobs:
  skill-guard:
    runs-on: ubuntu-latest
    env:
      AGENT_API_ENDPOINT: ${{ secrets.AGENT_API_ENDPOINT }}
      AGENT_API_KEY: ${{ secrets.AGENT_API_KEY }}

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install skill-guard
        run: pip install skill-guard

      - name: Detect changed skill
        id: changed
        run: |
          SKILL=$(git diff --name-only origin/main...HEAD | grep '^skills/' | head -1 | cut -d/ -f1-2)
          echo "skill=$SKILL" >> $GITHUB_OUTPUT

      - name: skill-guard check
        run: |
          skill-guard check ${{ steps.changed.outputs.skill }} \
            --against skills/ \
            --endpoint $AGENT_API_ENDPOINT \
            --format md > sg-report.md
          cat sg-report.md

      - name: Comment on PR
        if: always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const body = fs.readFileSync('sg-report.md', 'utf8');
            github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: '## skill-guard report\n\n' + body
            });
```

Add secrets to your repo: `Settings → Secrets → AGENT_API_ENDPOINT`, `AGENT_API_KEY`.

---

## Step 7: Set up weekly monitoring

Run via cron or CI for continuous drift detection. No built-in scheduler.

Create `.github/workflows/skill-guard-monitor.yml`:

```yaml
name: skill-guard Monitor

on:
  schedule:
    - cron: '0 9 * * 1'   # Monday 9am UTC
  workflow_dispatch:

jobs:
  monitor:
    runs-on: ubuntu-latest
    env:
      AGENT_API_ENDPOINT: ${{ secrets.AGENT_API_ENDPOINT }}
      AGENT_API_KEY: ${{ secrets.AGENT_API_KEY }}
      SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install skill-guard
      - run: |
          skill-guard monitor \
            --catalog skill-catalog.yaml \
            --endpoint $AGENT_API_ENDPOINT \
            --format md
```

---

## Step 8: Verify the Anthropic skills repo format

If you're using the [Anthropic skills repo](https://github.com/anthropics/skills), skill-guard is compatible out of the box — the SKILL.md format is the same. Run from the repo root:

```bash
# Clone the skills repo
git clone https://github.com/anthropics/skills
cd skills

pip install skill-guard
skill-guard init

# Validate an existing skill
skill-guard validate skills/skill-creator/

# Check all skills for conflicts
for skill in skills/*/; do
  echo "=== $skill ==="
  skill-guard conflict "$skill" --against skills/
done
```

---

## Troubleshooting

**`skill-guard test` fails: "Agent endpoint is required"**
→ Pass `--endpoint` or set `test.endpoint` in `skill-guard.yaml`

**Evals fail: response text doesn't contain expected strings**
→ Check what your agent actually returns: `skill-guard test ... --format json | jq '.result.results[].response_text'`

**Conflict score 1.0 with existing skill**
→ Your skill description overlaps too much. Narrow the trigger: add "Use when X but NOT when Y" to the description.

**Hook timeout**
→ Increase `reload_timeout_seconds` in config, or check your agent's `/health` endpoint responds correctly after skill injection.

---

## See also

- [Writing Evals](eval-authoring-guide.md)
- [Hook Scripts](hooks-guide.md)
- [CI Integration](ci-integration.md)
- [Configuration Reference](configuration-reference.md)
