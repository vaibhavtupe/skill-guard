# Basic Quickstart

Minimal local workflow:

```bash
python3 -m pip install skill-guard

# Initialize config in the current project
skill-guard init

# Validate a single skill directory
skill-guard validate ./skills/my-skill/

# Check for security issues
skill-guard secure ./skills/my-skill/

# Check for conflicts with other skills
skill-guard conflict ./skills/my-skill/ --against ./skills/
```

Each command takes a **single skill directory** (the folder that contains `SKILL.md`).
To validate multiple skills, loop over them:

```bash
for skill_dir in ./skills/*/; do
  skill-guard validate "$skill_dir"
done
```
