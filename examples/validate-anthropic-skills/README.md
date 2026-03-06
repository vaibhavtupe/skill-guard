# Validate Anthropic Skills

This example shows how to run `skill-guard` against the public `anthropics/skills` repository.

It will:
1. Clone `https://github.com/anthropics/skills` into `/tmp/anthropics-skills`.
2. Run `skill-guard validate` on `/tmp/anthropics-skills/skills`.
3. Optionally run `skill-guard conflict` on the same directory.

## Run

```bash
./run.sh
```

Or run optional conflict detection too:

```bash
./run.sh --with-conflict
```
