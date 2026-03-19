# Writing Evals for skill-guard

Evals are prompt/response test cases that verify your skill behaves correctly when loaded into a real agent. `skill-guard test` runs them against any OpenAI Responses API-compatible endpoint.

---

## Directory structure

Every skill that supports `skill-guard test` needs an `evals/` directory. You can use either `config.yaml` (prompt files) or `evals.json` (inline prompts):

```
my-skill/
├── SKILL.md
└── evals/
    ├── config.yaml          # test definitions (YAML)
    ├── evals.json           # test definitions (JSON)
    └── prompts/
        ├── basic.md         # one file per test case
        ├── edge-case.md
        └── out-of-scope.md
```

---

## config.yaml format

```yaml
tests:
  - name: basic-usage
    prompt_file: prompts/basic.md
    expect:
      contains: ["diagnosed", "latency"]        # all must appear in response
      not_contains: ["I cannot help", "error"]  # none may appear
      max_latency_ms: 3000                       # round-trip must be under 3s
      skill_triggered: my-skill                 # agent must call this tool

  - name: edge-case
    prompt_file: prompts/edge-case.md
    expect:
      contains: ["no active connections found"]

  - name: out-of-scope
    prompt_file: prompts/out-of-scope.md
    expect:
      not_contains: ["traceroute", "packet loss"]
      skill_not_triggered: my-skill             # skill must NOT be called
```

## evals.json format

`evals.json` lets you keep prompts inline. It expects `skill_name` and an `evals` list. Each entry needs a `prompt`. Use `expected_output` to describe what a correct response should look like; if no explicit checks are provided, the test is marked as **needs review** (non-blocking).

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "My AWS Direct Connect link keeps dropping packets. Can you help?",
      "expected_output": "diagnostic latency"
    },
    {
      "id": 2,
      "prompt": "Check if the skill routes to the right tool.",
      "expected_output": "Guidance plus a tool call",
      "expect": {
        "skill_triggered": "my-skill"
      }
    }
  ]
}
```

---

## Expect checks reference

| Field | Type | What it checks |
|---|---|---|
| `contains` | `list[str]` | All strings must appear somewhere in the response text |
| `not_contains` | `list[str]` | None of these strings may appear in the response text |
| `min_length` | `int` | Response text must be at least N characters |
| `max_latency_ms` | `int` | Round-trip time must not exceed N milliseconds |
| `skill_triggered` | `str` | A tool call with this exact name must appear in the response |
| `skill_not_triggered` | `str` | A tool call with this name must NOT appear |

All checks in an `expect` block must pass for the test to pass. A single failed check fails the test.

---

## Writing good prompts

Each `prompt_file` is plain text sent as the `input` field of a Responses API request.

**For positive tests (skill should trigger):**
```markdown
My AWS Direct Connect link keeps dropping packets intermittently.
Can you help diagnose what's causing the connectivity issue?
```

Write prompts that a real user would send. Avoid prompts that are so specific they only work with your exact implementation — test the intent, not the exact phrasing.

**For negative tests (skill should NOT trigger):**
```markdown
I need help setting up an Azure VPN gateway.
```

Out-of-scope prompts verify your skill doesn't over-trigger. Every skill should have at least one.

**For edge cases:**
```markdown
I'm seeing 0.01% packet loss. Is that significant?
```

Edge cases test boundary conditions — low-signal inputs, ambiguous requests, inputs that are technically in scope but at the margins.

---

## Recommended test coverage

| Test type | Min count | Purpose |
|---|---|---|
| Positive (skill triggers) | 2–3 | Core use cases actually work |
| Negative (skill doesn't trigger) | 1–2 | Skill doesn't over-trigger |
| Edge case | 1–2 | Boundary conditions handled |

A skill with only positive tests will pass `skill-guard test` but may cause conflicts with other skills in production. Always include at least one out-of-scope prompt.

---

## Running evals

```bash
# Against a local agent
skill-guard test ./skills/my-skill/ \
  --endpoint http://localhost:8000 \
  --model gpt-4.1

# Against a staging agent with API key
skill-guard test ./skills/my-skill/ \
  --endpoint https://staging-agent.example.com \
  --api-key $AGENT_API_KEY \
  --model gpt-4.1 \
  --format json

# As part of the full gate
skill-guard check ./skills/my-skill/ \
  --against ./skills/ \
  --endpoint http://localhost:8000

# Compare with-skill vs baseline behavior
skill-guard test ./skills/my-skill/ \
  --endpoint http://localhost:8000 \
  --model gpt-4.1 \
  --baseline
```

Baseline runs execute the same evals without injecting the skill (no hooks or copy),
then compare pass/fail outcomes and aggregate deltas.

---

## Workspace output (AgentSkills eval artifacts)

Use `--workspace` to write eval artifacts to disk in the AgentSkills-compatible
layout. Each run creates a new `iteration-N` directory with per-test outputs and
an aggregated `benchmark.json`.

```bash
skill-guard test ./skills/my-skill/ \
  --endpoint http://localhost:8000 \
  --model gpt-4.1 \
  --workspace ./eval-workspace
```

Directory layout:

```
./eval-workspace/
  iteration-1/
    with_skill/
      <test-name>/
        outputs/
          response.txt
          tool_calls.json
          timing.json
          grading.json
    benchmark.json
```

When `--baseline` is enabled, the iteration includes both `with_skill/` and
`without_skill/` directories, and `benchmark.json` captures the deltas.

---

## Debugging failing evals

Use `--format json` to get full response details:

```bash
skill-guard test ./skills/my-skill/ --endpoint http://localhost:8000 --format json | jq '.result.results[] | select(.passed == false)'
```

This shows the exact response text, tool calls, and which checks failed for each failing test.

---

## See also

- [Hook Scripts](hooks-guide.md) — set up agent state before evals run
- [CI Integration](ci-integration.md) — run evals in GitHub Actions
