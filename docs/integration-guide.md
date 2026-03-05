# End-to-End Integration Guide

How to integrate skill-gate into an existing skills repo and test against a real OpenAI Responses API-compatible agent.

---

## Overview

```
Your skills repo
├── skills/
│   ├── my-skill/
│   │   ├── SKILL.md
│   │   └── evals/
│   ├── another-skill/
│   └── skill-catalog.yaml     ← managed by skill-gate catalog
├── skill-gate.yaml            ← skill-gate config
└── .github/workflows/
    ├── skill-gate-ci.yml      ← PR gate (validate+secure+conflict+test)
    └── skill-gate-monitor.yml ← weekly health check
```

---

## Step 1: Initialize skill-gate in your repo

```bash
pip install agentskill-gate
cd your-skills-repo
skill-gate init
```

This creates `skill-gate.yaml` with commented defaults. Edit it:

```yaml
# skill-gate.yaml
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
  degrade_after_days: 7
  notify:
    slack_webhook: ${SLACK_WEBHOOK_URL}   # optional
```

---

## Step 2: Add evals to your skills

Each skill needs an `evals/` directory for `skill-gate test` to work. See [Writing Evals](eval-authoring-guide.md) for full details.

Minimum structure:

```
skills/my-skill/
├── SKILL.md
└── evals/
    ├── config.yaml
    └── prompts/
        ├── basic.md        # positive test — skill should trigger
        └── out-of-scope.md # negative test — skill should NOT trigger
```

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

---

## Step 3: What your agent needs to expose

skill-gate communicates with your agent via the **OpenAI Responses API** format. Your agent needs two endpoints:

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

Response format skill-gate parses:
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

skill-gate extracts:
- **Tool calls** from `output[].type == "tool_call"` → `output[].name`
- **Response text** from `output[].type == "message"` → `output[].content[].text`

Any OpenAI-compatible agent (OpenAI Assistants, custom FastAPI wrapper, LangChain agent with Responses API adapter) works as-is.

---

## Step 4: Run locally first

```bash
# Export your agent config
export AGENT_API_ENDPOINT=http://localhost:8000
export AGENT_API_KEY=your-key   # omit if no auth

# 1. Validate skill format
skill-gate validate skills/my-skill/

# 2. Scan for security issues
skill-gate secure skills/my-skill/

# 3. Check for conflicts with other skills
skill-gate conflict skills/my-skill/ --against skills/

# 4. Run evals against your agent
skill-gate test skills/my-skill/ \
  --endpoint $AGENT_API_ENDPOINT \
  --api-key $AGENT_API_KEY \
  --model gpt-4.1

# 5. Run everything in one command
skill-gate check skills/my-skill/ \
  --against skills/ \
  --endpoint $AGENT_API_ENDPOINT
```

All commands exit 0 on pass, 1 on failure — scriptable in any CI system.

---

## Step 5: Register skills in the catalog

After a skill passes all checks, register it:

```bash
skill-gate catalog register skills/my-skill/ --catalog skill-catalog.yaml
```

This creates/updates `skill-catalog.yaml` with the skill's metadata, quality score, and stage (`staging` by default).

```bash
# View catalog
skill-gate catalog list

# Promote to production (manual, after your review process)
# Edit skill-catalog.yaml: change stage: staging → stage: production
```

Commit `skill-catalog.yaml` to your repo — it's the source of truth for deployed skills.

---

## Step 6: Set up CI (GitHub Actions)

Create `.github/workflows/skill-gate-ci.yml`:

```yaml
name: skill-gate CI

on:
  pull_request:
    paths:
      - 'skills/**'

jobs:
  skill-gate:
    runs-on: ubuntu-latest
    env:
      AGENT_API_ENDPOINT: ${{ secrets.AGENT_API_ENDPOINT }}
      AGENT_API_KEY: ${{ secrets.AGENT_API_KEY }}

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install skill-gate
        run: pip install agentskill-gate

      - name: Detect changed skill
        id: changed
        run: |
          SKILL=$(git diff --name-only origin/main...HEAD | grep '^skills/' | head -1 | cut -d/ -f1-2)
          echo "skill=$SKILL" >> $GITHUB_OUTPUT

      - name: skill-gate check
        run: |
          skill-gate check ${{ steps.changed.outputs.skill }} \
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
              body: '## skill-gate report\n\n' + body
            });
```

Add secrets to your repo: `Settings → Secrets → AGENT_API_ENDPOINT`, `AGENT_API_KEY`.

---

## Step 7: Set up weekly monitoring

Create `.github/workflows/skill-gate-monitor.yml`:

```yaml
name: skill-gate Monitor

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
      - run: pip install agentskill-gate
      - run: |
          skill-gate monitor \
            --catalog skill-catalog.yaml \
            --endpoint $AGENT_API_ENDPOINT \
            --format md
```

---

## Step 8: Verify the Anthropic skills repo format

If you're using the [Anthropic skills repo](https://github.com/anthropics/skills), skill-gate is compatible out of the box — the SKILL.md format is the same. Run from the repo root:

```bash
# Clone the skills repo
git clone https://github.com/anthropics/skills
cd skills

pip install agentskill-gate
skill-gate init

# Validate an existing skill
skill-gate validate skills/skill-creator/

# Check all skills for conflicts
for skill in skills/*/; do
  echo "=== $skill ==="
  skill-gate conflict "$skill" --against skills/
done
```

---

## Troubleshooting

**`skill-gate test` fails: "Agent endpoint is required"**
→ Pass `--endpoint` or set `test.endpoint` in `skill-gate.yaml`

**Evals fail: response text doesn't contain expected strings**
→ Check what your agent actually returns: `skill-gate test ... --format json | jq '.result.results[].response_text'`

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
