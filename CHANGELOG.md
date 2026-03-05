# Changelog

## v0.3.0 — 2026-03-05

### Phase 3: Monitoring + Lifecycle

**New:**
- `skill-gate monitor` — full health check pipeline across all catalog skills
- `lifecycle.py` — automated stage transitions (production → degraded → deprecated), staleness checks, CODEOWNERS/MAINTAINERS ownership validation
- `notifier.py` — Slack webhook alerts + GitHub Issues creation (deduplicates open issues)
- `output/html.py` — HTML health report with inline CSS, color-coded status cards
- `.github/workflows/skill-gate-monitor.yml` — weekly scheduled monitoring (Monday 9am UTC)

**Tests:** 64 passing, 81.57% coverage

---

## v0.2.0 — 2026-03-05

### Phase 2: Integration Testing + Catalog

**New:**
- `skill-gate test` — runs evals against real agent via OpenAI Responses API
- `skill-gate catalog` — register, list, search, stats subcommands
- `skill-gate check` — full pipeline: validate → secure → conflict → test in one pass
- `agent_runner.py` — async eval execution, pre/post hook support, health polling
- `catalog_manager.py` — atomic YAML catalog read/write, stage management
- `docs/ci-integration.md` — full GitHub Actions integration guide
- CI: lint → unit-tests → integration-tests pipeline

**Tests:** 50 passing, 80.82% coverage

---

## v0.1.0 — 2026-03-05

### Phase 1: Static Analysis Foundation

**New:**
- `skill-gate validate` — schema validation, description quality, eval presence checks
- `skill-gate secure` — prompt injection detection, scope violation scanning
- `skill-gate conflict` — TF-IDF cosine similarity conflict detection
- `skill-gate init` — project scaffold (skill-gate.yaml + CI workflow)
