# Changelog

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
