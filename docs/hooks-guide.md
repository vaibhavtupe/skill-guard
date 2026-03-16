# Hook Scripts

Hook scripts let you prepare your agent before evals run and clean up after. Common uses: loading a skill into a running agent, resetting agent state, restarting a service.

---

## When you need hooks

`skill-guard test` sends prompts directly to your agent endpoint — it does not deploy the skill for you. If your agent needs to load the skill before it can use it, you need a pre-test hook to do that deployment.

If your agent loads skills at startup from a directory, hooks are the way to inject the skill under test before evals run.

---

## Configuration

```yaml
# skill-guard.yaml
test:
  endpoint: http://localhost:8000
  model: gpt-4.1
  injection:
    pre_test_hook: hooks/deploy-skill.sh    # runs before evals
    post_test_hook: hooks/remove-skill.sh   # always runs after evals (even on failure)
  reload_timeout_seconds: 30               # max wait for agent to become healthy after hook
```

---

## Hook contract

| Property | Detail |
|---|---|
| Arguments | `$1` = skill path (absolute), `$2` = agent endpoint URL |
| Exit code | `0` = success, non-zero = abort test run |
| Stdout/stderr | Captured and shown on hook failure |
| Post-hook | Always runs — even if evals fail or pre-hook fails (cleanup must be safe) |

---

## Example: directory copy

The simplest approach — copy the skill into the agent's skills directory, then wait for it to reload:

```bash
#!/usr/bin/env bash
# hooks/deploy-skill.sh
set -euo pipefail

SKILL_PATH="$1"
AGENT_SKILLS_DIR="${AGENT_SKILLS_DIR:-/app/skills}"

cp -r "$SKILL_PATH" "$AGENT_SKILLS_DIR/"
echo "Deployed $(basename "$SKILL_PATH") to $AGENT_SKILLS_DIR"
```

```bash
#!/usr/bin/env bash
# hooks/remove-skill.sh
set -euo pipefail

SKILL_PATH="$1"
AGENT_SKILLS_DIR="${AGENT_SKILLS_DIR:-/app/skills}"

rm -rf "$AGENT_SKILLS_DIR/$(basename "$SKILL_PATH")"
echo "Removed $(basename "$SKILL_PATH") from $AGENT_SKILLS_DIR"
```

---

## Example: HTTP API injection

If your agent exposes an API to load/unload skills dynamically:

```bash
#!/usr/bin/env bash
# hooks/deploy-skill.sh
set -euo pipefail

SKILL_PATH="$1"
ENDPOINT="$2"
SKILL_NAME=$(basename "$SKILL_PATH")

curl -sf -X POST "$ENDPOINT/admin/skills/load" \
  -H "Content-Type: application/json" \
  -d "{\"path\": \"$SKILL_PATH\"}" \
  || { echo "Failed to load skill via API"; exit 1; }

echo "Loaded $SKILL_NAME via agent API"
```

---

## Example: Docker container

If your agent runs in Docker and you need to copy the skill in and restart:

```bash
#!/usr/bin/env bash
# hooks/deploy-skill.sh
set -euo pipefail

SKILL_PATH="$1"
CONTAINER="${AGENT_CONTAINER:-my-agent}"

docker cp "$SKILL_PATH" "$CONTAINER:/app/skills/"
docker restart "$CONTAINER"
echo "Restarted $CONTAINER with $(basename "$SKILL_PATH")"
```

---

## Health check after hook

After the pre-test hook runs, skill-guard can optionally execute `test.reload_command`, wait `reload_wait_seconds`, then poll `GET {endpoint}{reload_health_check_path}` until it returns 200 or `reload_timeout_seconds` is exceeded. The default health path is `/health`.

```python
# FastAPI example
@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## Hook failure behavior

| Scenario | What happens |
|---|---|
| Pre-hook exits non-zero | Test run aborted, post-hook still runs, exit code 5 |
| Agent doesn't become healthy within timeout | Test run aborted, post-hook still runs, exit code 6 |
| Eval test fails | Post-hook still runs, exit code 1 |
| Post-hook exits non-zero | Logged as warning, exit code from evals is preserved |

---

## Debugging hooks

Run hooks manually to verify they work before wiring into skill-guard:

```bash
chmod +x hooks/deploy-skill.sh
./hooks/deploy-skill.sh ./skills/my-skill http://localhost:8000
echo "exit: $?"
```

---

## See also

- [Writing Evals](eval-authoring-guide.md)
- [CI Integration](ci-integration.md) — hooks in GitHub Actions pipelines
