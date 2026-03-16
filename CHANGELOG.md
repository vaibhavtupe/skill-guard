## v0.5.0 — 2026-03-16

### New Features & Fixes

- **feat(#65): pre-commit hooks** — `.pre-commit-hooks.yaml` ships with the package. Three hooks: `skill-guard-validate`, `skill-guard-secure`, `skill-guard-check`. One paste into `.pre-commit-config.yaml` enforces validation at every commit.
- **feat(#69): Anthropic AgentSkills spec compliance validator** — `skill-guard validate` now checks 8 spec rules: required frontmatter fields, 500-line body limit, description quality + trigger keywords, evals.json schema, binary reference existence. Opt-out via `validate.anthropic_spec: false`.
- **feat(#66): `skill-guard fix`** — auto-repairs deterministic validation issues (missing frontmatter stubs, trailing whitespace, tabs → spaces). `--check` mode for dry-run in CI (exits 1 when fixes are available).
- **feat(#67): `skill-guard init --template`** — scaffolds Anthropic-spec compliant skills from named templates: `base`, `weather-tool`, `search-tool`. Generated skills pass `validate` at 100/100 out of the box. `--list-templates` to enumerate.
- **docs(#64): GitHub Action usage** — README now documents `vaibhavtupe/skill-guard-action@v1` with full input/output reference.
- **fix(#70): README honesty** — corrected `--agent-url` → `--endpoint`, removed overstatements on `check`/`test`/`monitor`/`catalog`, documented all 6 exit codes, noted embeddings/LLM as planned features.

**Stats:** 103 tests passing | 82.80% coverage | 48 files changed | 1,355 insertions

---

# Changelog

## v0.4.4 — 2026-03-06

### Bug Fixes
- **fix(#51): wire agent evals into check command** — `skill-guard check --endpoint <url>` now actually runs OpenAI Responses API evals instead of silently skipping them. Test result included in output payload. Exit code 1 on eval failure.

---

## v0.4.3 — 2026-03-06

### Bug Fixes

- **Fix crash on startup with typer <0.13** — `Path | None` union type not supported by typer 0.9.x; tightened minimum to `typer>=0.13.0` (closes #47)
- **Fix all `skill-gate` → `skill-guard` naming** throughout Python source, config, init, tests, and output headers (closes #44)
- **Fix example command syntax** — examples used non-existent `--dir` flag; corrected to positional `SKILL_PATH` with multi-skill loop pattern (closes #45)
- **Add `examples/` directory** — `validate-anthropic-skills/` and `basic-quickstart/` with accurate working commands (closes #42)
- **Fix README naming** — removed stale `agentskill-guard` references; updated example output to match actual table format (closes #41)

---

## v0.3.0 — 2026-03-05

### Phase 3: Monitoring + Lifecycle

**New:**
- `skill-guard monitor` — full health check pipeline across all catalog skills
- `lifecycle.py` — automated stage transitions (production → degraded → deprecated), staleness checks, CODEOWNERS/MAINTAINERS ownership validation
- `notifier.py` — Slack webhook alerts + GitHub Issues creation (deduplicates open issues)
- `output/html.py` — HTML health report with inline CSS, color-coded status cards
- `.github/workflows/skill-guard-monitor.yml` — weekly scheduled monitoring (Monday 9am UTC)

**Tests:** 64 passing, 81.57% coverage

---

## v0.2.0 — 2026-03-05

### Phase 2: Integration Testing + Catalog

**New:**
- `skill-guard test` — runs evals against real agent via OpenAI Responses API
- `skill-guard catalog` — register, list, search, stats subcommands
- `skill-guard check` — full pipeline: validate → secure → conflict → test in one pass
- `agent_runner.py` — async eval execution, pre/post hook support, health polling
- `catalog_manager.py` — atomic YAML catalog read/write, stage management
- `docs/ci-integration.md` — full GitHub Actions integration guide
- CI: lint → unit-tests → integration-tests pipeline

**Tests:** 50 passing, 80.82% coverage

---

## v0.1.0 — 2026-03-05

### Phase 1: Static Analysis Foundation

**New:**
- `skill-guard validate` — schema validation, description quality, eval presence checks
- `skill-guard secure` — prompt injection detection, scope violation scanning
- `skill-guard conflict` — TF-IDF cosine similarity conflict detection
- `skill-guard init` — project scaffold (skill-guard.yaml + CI workflow)

## v0.3.2 — 2026-03-05

### Bug fixes & docs

- Fix: wrong Anthropic skill-creator URL in README
- Fix: README Documentation section linked to non-existent files
- Docs: add `docs/eval-authoring-guide.md` — eval authoring reference
- Docs: add `docs/hooks-guide.md` — pre/post hook scripts guide
- Docs: add `docs/integration-guide.md` — end-to-end setup with real Responses API agent

## v0.4.0 — 2026-03-05

### Project rename finalized

- PyPI package: `skill-guard`
- CLI command: `skill-guard`
- Python package: `skill_guard`
- GitHub repo: `vaibhavtupe/skill-guard`
- All functionality unchanged — pure rename
