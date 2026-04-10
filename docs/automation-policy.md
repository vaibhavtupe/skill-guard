# Automation Policy (PM ↔ Dev)

**Purpose:** Make delivery fully automated with minimal human intervention.

## 1) Single Source of Truth
- **ROADMAP.md is canonical** for scope + priority + acceptance criteria.
- README/config/docs are **outputs**, not inputs.
- Any conflict → update ROADMAP.md first, then sync docs.
- Release readiness is checked with `docs/release-gate.md`.

## 2) PM Responsibilities
- Convert roadmap scope into GitHub issues with **exact acceptance criteria**.
- Each issue must include:
  - Scope bullets (from ROADMAP)
  - Acceptance criteria checklist
  - Tests required
  - Files/functions to touch
  - “Spec compliance” updates (README/config/docs)
- Every release issue must map back to a specific version section in `ROADMAP.md`.

## 3) Dev Responsibilities (Definition of Done)
Dev may only mark complete when ALL are true:
- All acceptance criteria checked off
- Tests pass (`pytest`)
- Coverage ≥ 80%
- Spec compliance checklist green (README/config/template reflect reality)
- No roadmap drift (ROADMAP scope still matches code)

## 4) Spec Compliance Checklist (required)
- README claims match implemented feature flags
- Config template matches actual config fields
- CLI help strings match options implemented
- Any feature described in README exists or is explicitly marked “planned”

## 5) Conflict Resolution Loop
- If PM detects mismatch, open a **Spec Decision** issue
- Dev does **not proceed** until the decision is resolved
- Decisions update ROADMAP.md first

## 6) Release Gate
- No release tag until:
  - `pytest` green (or documented equivalent for docs/process-only changes)
  - Spec compliance green
  - ROADMAP scope matches shipped behavior
  - `docs/release-gate.md` is completed

## 7) Operating Rules
- Start planning in `ROADMAP.md`, not in README.
- If a feature is partial, planned, or experimental, label it explicitly in user-facing docs.
- If shipped behavior changes during execution, update `ROADMAP.md` before updating README/config/docs.
- Release notes and changelog should describe shipped behavior, not aspirational scope.

---

**Portability:** This policy is generic—copy to any repo and change the Roadmap path/name.
