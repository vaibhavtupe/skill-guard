# Getting Started

## Install

```bash
pip install agentskill-gate
```

Optional embeddings (Phase 3):

```bash
pip install agentskill-gate[embeddings]
```

## Quick Start

```bash
# Initialize config
skill-gate init

# Validate a skill
skill-gate validate ./skills/my-skill/

# Scan for security issues
skill-gate secure ./skills/my-skill/

# Check conflicts
skill-gate conflict ./skills/my-skill/ --against ./skills/

# Run the full gate (validate + secure + conflict)
skill-gate check ./skills/my-skill/ --against ./skills/
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
- Add evals in `evals/` for Phase 2 integration tests
