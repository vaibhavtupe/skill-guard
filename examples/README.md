# Examples — Running skill-guard Against Real Skills

These examples are adapted from the [Anthropic skills repository](https://github.com/anthropics/skills) and demonstrate how to run skill-guard against real-world Agent Skills.

## Quick Demo

```bash
pip install skill-guard
git clone https://github.com/vaibhavtupe/skill-guard
cd skill-guard
skill-guard validate examples/pdf/
skill-guard check examples/pdf/ --against examples/
```

## What You Will See

```text
$ skill-guard validate examples/skill-creator/
                      skill-guard validate — skill-creator
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check                     ┃ Result                                           ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ skill_md_exists           │ ✅ SKILL.md found                                │
│ valid_yaml_frontmatter    │ ✅ Valid YAML frontmatter                        │
│ name_field_present        │ ✅ name: skill-creator                           │
│ description_field_present │ ✅ description field present                     │
│ directory_name_matches    │ ✅ Directory name 'skill-creator' matches skill  │
│                           │ name                                             │
│ name_format_valid         │ ✅ Name 'skill-creator' uses valid characters    │
│ description_min_length    │ ✅ Description length 320 chars >= 20            │
│ description_max_length    │ ✅ Description length 320 chars <= 500           │
│ description_trigger_hint  │ ✅ Description contains trigger hint ('Use       │
│                           │ when')                                           │
│ description_not_generic   │ ✅ Description is specific and informative       │
│ body_not_empty            │ ✅ SKILL.md body has content                     │
│ body_under_max_lines      │ ✅ Body length 3 lines <= 500                    │
│ scripts_executable        │ ✅ No scripts                                    │
│ references_exist          │ ✅ No references directory                       │
│ no_broken_body_paths      │ ✅ No broken relative paths in SKILL.md body     │
│ evals_directory_exists    │ ⚠️ No evals/ directory found                     │
│                           │ → Create evals/config.yaml with test cases.      │
│                           │ Required for integration testing (skill-guard     │
│                           │ test). See docs/eval-authoring-guide.md          │
│ metadata_has_author       │ ❌ Missing 'author' in metadata                  │
│                           │ → Add metadata:\n  author: your-team-name        │
│ metadata_has_version      │ ❌ Missing 'version' in metadata                 │
│                           │ → Add metadata:\n  version: "1.0"                │
└───────────────────────────┴──────────────────────────────────────────────────┘
Score: 90/100 | Grade: A | Blockers: 2 | Warnings: 1

$ skill-guard validate examples/pdf/
                           skill-guard validate — pdf
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check                     ┃ Result                                           ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ skill_md_exists           │ ✅ SKILL.md found                                │
│ valid_yaml_frontmatter    │ ✅ Valid YAML frontmatter                        │
│ name_field_present        │ ✅ name: pdf                                     │
│ description_field_present │ ✅ description field present                     │
│ directory_name_matches    │ ✅ Directory name 'pdf' matches skill name       │
│ name_format_valid         │ ✅ Name 'pdf' uses valid characters              │
│ description_min_length    │ ✅ Description length 437 chars >= 20            │
│ description_max_length    │ ✅ Description length 437 chars <= 500           │
│ description_trigger_hint  │ ⚠️ Description missing trigger hint              │
│                           │ → Add a 'Use when...' phrase to help the agent   │
│                           │ know when to activate this skill                 │
│ description_not_generic   │ ⚠️ Description contains generic phrases: 'this   │
│                           │ skill'                                           │
│                           │ → Be specific about what this skill does and     │
│                           │ when to use it                                   │
│ body_not_empty            │ ✅ SKILL.md body has content                     │
│ body_under_max_lines      │ ✅ Body length 234 lines <= 500                  │
│ scripts_executable        │ ✅ No scripts                                    │
│ references_exist          │ ✅ No references directory                       │
│ no_broken_body_paths      │ ❌ Broken relative paths in body: REFERENCE.md,  │
│                           │ FORMS.md, reader.pages, page.extra, writer.add,  │
│                           │ writer.write, reader.metad, page.rotat,          │
│                           │ pdfplumber.open, pdf.pages, pd.DataF,            │
│                           │ all_tables.appen, pd.conca, combined_df.to,      │
│                           │ reportlab.lib.pages, reportlab.pdfge,            │
│                           │ canvas.Canva, c.drawS, c.line, c.save,           │
│                           │ reportlab.platy, reportlab.lib.style,            │
│                           │ story.appen, doc.build, input.pdf, output.txt,   │
│                           │ file1.pdf, file2.pdf, merged.pdf, pages1-5.pdf,  │
│                           │ pages6-10.pdf, output.pdf, encrypted.pdf,        │
│                           │ decrypted.pdf, rotated.pdf, pytesseract.image,   │
│                           │ page.merge, output_prefix-000.jpg,               │
│                           │ output_prefix-001.jpg, writer.encry              │
│                           │ → Fix the paths or remove the references         │
│ evals_directory_exists    │ ⚠️ No evals/ directory found                     │
│                           │ → Create evals/config.yaml with test cases.      │
│                           │ Required for integration testing (skill-guard     │
│                           │ test). See docs/eval-authoring-guide.md          │
│ metadata_has_author       │ ❌ Missing 'author' in metadata                  │
│                           │ → Add metadata:\n  author: your-team-name        │
│ metadata_has_version      │ ❌ Missing 'version' in metadata                 │
│                           │ → Add metadata:\n  version: "1.0"                │
└───────────────────────────┴──────────────────────────────────────────────────┘
Score: 74/100 | Grade: C | Blockers: 3 | Warnings: 3

$ skill-guard secure examples/skill-creator/
 skill-guard secure —
    skill-creator
┏━━━━━━━━━━┳━━━━━━━━━┓
┃ Severity ┃ Finding ┃
┡━━━━━━━━━━╇━━━━━━━━━┩
└──────────┴─────────┘
Critical: 0 | High: 0 | Medium: 0 | Low: 0

$ skill-guard conflict examples/skill-creator/ --against examples/
skill-guard conflict
  — skill-creator
┏━━━━━━━┳━━━━━━━━━┓
┃ Match ┃ Details ┃
┡━━━━━━━╇━━━━━━━━━┩
└───────┴─────────┘
High conflicts: 0 | Medium conflicts: 0
```

## Skills in This Directory

| Skill | Source | Description |
| --- | --- | --- |
| `skill-creator` | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/skill-creator) | Create new skills, improve existing skills, and evaluate/optimize skill performance. |
| `pdf` | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/pdf) | PDF processing operations including extraction, merging, splitting, OCR, and form work. |
| `mcp-builder` | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/mcp-builder) | Guide for designing and implementing high-quality MCP servers in TypeScript or Python. |

## Running Against Your Own Skills

```bash
skill-guard validate /path/to/your/skills/my-skill/
skill-guard secure /path/to/your/skills/my-skill/
skill-guard check /path/to/your/skills/my-skill/ --against /path/to/your/skills/
```
