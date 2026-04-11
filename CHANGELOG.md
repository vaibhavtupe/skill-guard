# Changelog

## v0.8.0 — 2026-04-11

### Default PR Gate

- **feat(#109): repo-aware multi-skill PR checks** — `check --changed` now resolves changed skills directly from the repo, supports aggregate multi-skill evaluation, and handles zero-change, rename, and delete flows cleanly.
- **feat(#110): canonical GitHub Actions PR gate** — shipped one documented PR-native CI path with markdown and JSON output contracts plus artifact/reporting expectations.
- **docs(#111): `check` as the default workflow** — CLI help and docs now lead with `check`, with advanced workflows explicitly demoted behind the default path.
- **fix(#112): spec and docs alignment** — `evals/evals.json` is now the preferred format end to end, parser precedence is explicit, and placeholder or experimental behavior is labeled clearly.
- **fix(#113): offline-first remediation and lower false-positive friction** — summaries now distinguish blockers vs warnings cleanly, markdown includes remediation guidance, and comment-only external URLs in scripts no longer trip the security finding.
- **feat(#114): deterministic eval CI contract** — `skill-guard test` now emits stable run metadata and setup-failure artifacts, and setup/health failures carry actionable remediation guidance.
- **docs: closeout alignment** — README guidance now matches the shipped deterministic CI eval path and release-gate expectations.
- **docs(#115): roadmap and release gate** — added `ROADMAP.md` as the planning source of truth plus a release-gate checklist tied to shipped behavior.

### Release Notes

- `skill-guard` now presents a coherent pre-merge default workflow for shared skill repositories.
- The static gate remains useful without live eval setup.
- Live evals now have one recommended CI path and better debugging artifacts when setup fails.

---

## v0.7.2 — 2026-03-26

### Bug Fixes

- **fix: dotted identifiers in code** — ignore inline dotted identifiers like `pagination.total` in `no_broken_body_paths` (unless they look like actual file paths).

---

## v0.7.1 — 2026-03-26

### Bug Fixes

- **fix(#107): dotted API field references** — avoid false positives in `no_broken_body_paths` for dotted API fields like `response.output_text`; add regression tests.

---

## v0.7.0 — 2026-03-19

### New Features & Fixes

- **feat(#96): evals.json support** — parse and validate `evals/evals.json` alongside existing config.yaml flow; inline prompts supported.
- **feat(#100): expected_output evals** — store expected_output and mark review-only when no assertions; allow expect blocks in evals.json.
- **feat(#97): baseline eval runs** — optional with-skill vs without-skill comparison and summary output.
- **feat(#98): eval workspace artifacts** — iteration-N directories, per-test outputs, and benchmark.json; baseline writes with_skill/ and without_skill/.
- **docs(#99): eval iteration loop guidance** — aligned docs with Anthropic skill-creator workflow and clarified evals.json vs config.yaml precedence.
- **fix: lint** — ruff UP037 cleanup.

---

## v0.6.0 — 2026-03-16

### New Features & Fixes

- **feat(#74): embeddings-based conflict detection** — `skill-guard conflict --method embeddings` via `sentence-transformers` (`all-MiniLM-L6-v2`). Catches semantic overlap TF-IDF misses. Optional extra: `pip install skill-guard[embeddings]`. Clear error with install hint when dep is missing. `--offline` flag falls back to tfidf in air-gapped CI.
- **feat(#75): real prompt injection pattern library** — 15 new `INJECT-*` patterns covering instruction overrides, role hijack, exfiltration hooks, jailbreak scaffolding, zero-width characters, context stuffing, privilege escalation. Zero false positives on 15 OpenClaw production skills.
- **feat(#76): `skill-guard suppress`** — structured false-positive reporting. Inserts inline disable comment in SKILL.md, records to `skill-guard.yaml` with mandatory reason + timestamp. `validate --show-suppressed` lists all records.
- **fix(#71): replace `datetime.utcnow()`** — 20 deprecation warnings eliminated.
- **fix(#72): `fix --check` output** — no longer says "0 fixes applied" when fixes are available in dry-run mode.
- **test(#73): pre-commit integration tests** — 17 integration tests for the `skill-guard-pre-commit` entrypoint.

**Stats:** 160 tests passing | 0 deprecation warnings

---

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
