# Getting Started

## Install

```bash
pip install skill-guard
```

Optional embeddings:

```bash
pip install skill-guard[embeddings]
```

## Quick Start

```bash
# Initialize config
skill-guard init

# Run the default pre-merge gate
skill-guard check ./skills/my-skill/ --against ./skills/
```

If you only remember one command, use `check`. It is the default workflow and the fastest way to get value from the tool.

## Inspect Individual Checks

Use these when you need to debug part of the gate:

```bash
skill-guard validate ./skills/my-skill/
skill-guard secure ./skills/my-skill/
skill-guard conflict ./skills/my-skill/ --against ./skills/
```

## Example Output

### validate
```
✅ skill_md_exists: SKILL.md found
✅ valid_yaml_frontmatter: Valid YAML frontmatter
⚠️ description_trigger_hint: Description missing trigger hint

Score: 86/100 | Grade: B | Blockers: 0 | Warnings: 1
```

### secure
```
❌ CREDENTIALS [CRED-001] in SKILL.md:12
Possible API key in plaintext
→ Use environment variables: ${API_KEY}

Critical: 1 | High: 0 | Medium: 0 | Low: 0
```

### conflict
```
❌ network-diagnostics (score=0.84)
Overlap: diagnose + connectivity + issues
Suggestions: merge, narrow, exclude hints
```

## Next

- See [Configuration Reference](configuration-reference.md)
- Add evals in `evals/` if you want optional live eval coverage with `skill-guard test`
