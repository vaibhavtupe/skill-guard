# skill-guard v1 Relaunch — Design

**Status:** Approved for planning
**Date:** 2026-08-05
**Supersedes:** ROADMAP.md's v0.8.0/v0.9 scope where it conflicts with this document

## 1. Problem and evidence

Agent Skills (SKILL.md-based) are ungoverned once more than one person contributes to a
shared repo. External research confirms the risk is real:

- Snyk's ToxicSkills study found prompt injection in 36% of skills studied, with 1,467
  malicious payloads found across the ecosystem and 13.4% of skills carrying at least one
  critical-severity issue.
- Datadog Security Labs published dynamic-context supply-chain risk research for skills in
  coding agents.
- Anthropic ships no official validation or gating tool.

However, single-skill linting/scoring is no longer an empty space:

| Project | Lang | Stars (2026-08) | Covers |
|---|---|---|---|
| agent-ecosystem/skill-validator | Go | 214 | spec compliance, content quality, LLM scoring, GH annotations. No security scan, no conflict detection. |
| thedaviddias/skill-check | TS | 188 | scoring, auto-fix, SARIF, integrated security scan (mcp-scan) |
| vaibhavtupe/skill-guard | Python | 4 | only project with repo-aware PR gating + cross-skill conflict detection |

Security scanning specifically is crowded and getting more so (Snyk, Datadog, mcp-scan,
multiple new entrants) — not a defensible wedge for a small OSS project to win.

**Decision:** skill-guard does not compete on single-skill linting or security scanning.
It owns the problem nobody else addresses: gating a *shared team repo* of skills at PR time,
including detecting when two skills conflict.

## 2. Positioning

> **skill-guard is the PR gate for your team's Agent Skills repo.**

Not a linter (skill-validator owns that). Not a security scanner (crowded, hard to win).
skill-guard is what a team installs once more than one person contributes skills to a
shared repository: it gates PRs on conflicts, spec violations, and risky changes —
repo-aware, offline-first, deterministic.

Primary user: **teams with a shared `skills/` repo** (platform/AI-enablement teams), reached
primarily through a GitHub Action, with the CLI as the local companion tool.

### Product principles

1. **Green by default on real skills.** Anthropic's own skills repo must pass `skill-guard check`
   cleanly out of the box. This is a permanent CI regression test (see §7), not a one-time fix.
2. **Deterministic, offline, fast core.** No API key required, no model downloads, no
   phone-home network calls. Target: <10 MB install, <200 ms cold-start CLI invocation
   (current: 241 MB install, ~2.2s startup).
3. **Every finding names the file, the reason, and the fix.** Nothing blocks a merge without
   a specific, actionable remediation. Every blocking finding must be suppressible via a
   recorded, reviewable exception (not silent).

## 3. Scope cut

Delete from `main` for v1 (history preserves them; may return later as opt-in plugins,
not core):

- `skill_guard/engine/agent_runner.py`, `engine/test_injection.py`, `commands/test.py`,
  `output/workspace.py` — the live-eval harness. It targets the OpenAI Responses API in a
  project branded around Anthropic Agent Skills, includes a `git_push` injection mode that
  force-pushes into the user's agent repo, and its assertion model (substring
  contains/not_contains, latency) is not a credible eval story.
- `commands/monitor.py`, `engine/lifecycle.py`, `engine/notifier.py` — scheduled
  re-evaluation, lifecycle states, Slack webhooks. This is scale-org governance tooling
  shipped before the core gate is trustworthy.
- `commands/catalog.py`, `engine/catalog_manager.py` — YAML catalog with no approval
  workflow (README already admits this isn't implemented).
- `output/semantics.py` (the five-state "trust vocabulary" layer) and `output/html.py`.
- PyPI update-check network call in `main.py`.
- Dead config surface: `use_snyk_scan`, `post_pr_comment`, unimplemented `llm_*` conflict
  knobs beyond what §5 actually ships.

**Dependency diet.** Remove `scikit-learn` (~184 MB, pulled in solely for TF-IDF cosine
similarity on two short strings) and `python-levenshtein` (declared, never imported; the
code already uses `difflib`). Keep `typer`, `pydantic`, `ruamel.yaml`, `rich`. Add
`rapidfuzz` for name-similarity (replaces `difflib`, already lighter and faster). `httpx`
moves into the `[llm]` extra, used only by the opt-in LLM conflict tier.

What survives unchanged in spirit: the engine/commands/output module boundaries, the
Pydantic models layer, `parser.py`'s error messages, `fixer.py`'s conservative
apply-only-unambiguous-fixes philosophy, and `repo_targets.py`'s git-diff machinery (once
its bugs are fixed — see §6).

## 4. Spec validator rebuild

Current `spec_validator.py` diverges from the actual agentskills.io / Anthropic spec in
both directions. Rebuild to check what the spec actually constrains:

- `name`: present, ≤ 64 characters, matches directory name (existing check, keep).
- `description`: present, ≤ 1024 characters (not the current invented 500-char default).
- `allowed-tools`: parse the real hyphenated frontmatter key via a proper Pydantic field
  alias (`SkillMetadata.allowed_tools` currently has no alias and silently drops the field —
  this is a correctness bug, not a scope question, and is fixed regardless of what else ships).
- Unknown top-level frontmatter keys: warning, not blocker.
- `compatibility` / `license` fields: parse if present, no opinion if absent.

Anything that is a skill-guard convention rather than a spec requirement (evals/ directory
structure, 20-word description minimum, "Use when" exact-phrase requirement) is renamed out
of anything labeled `[anthropic-spec]` and demoted to an advisory quality check (§ below),
never a blocker.

**Quality score** becomes explicitly advisory: computed only over checks that can actually
fail (drop the ~34% currently-unfalsifiable weight from checks the parser already
guarantees), and spec blockers and quality warnings are reported separately — no more
"Grade A, Status: failed" contradictions dropped, no more duplicate checks for the same
condition (body-length, trigger-hint) disagreeing with each other.

**Default-severity flip:** `require_author_in_metadata` and `require_version_in_metadata`
default to `false` (informational, not blocking). These aren't spec requirements and
Anthropic's own skills don't carry them — defaulting them to blocking is why a clean
Anthropic-style skill currently fails the gate.

## 5. Conflict engine (the differentiator)

Tiered design — deterministic core, optional semantic upgrade:

**Tier 1 — default, offline, deterministic.**
Replace 2-document TF-IDF (which the review showed scores genuinely overlapping skills at
~0.39, under threshold) with an explainable lexical/structural approach:
- Extract trigger phrases from each description (the "Use when…" / "Trigger on…" clause).
- Score overlap on normalized trigger tokens, shared domain nouns, and name similarity
  (rapidfuzz), with skill-family awareness so `deploy-staging` / `deploy-prod` and
  `earnings-preview` / `earnings-review` are not flagged as name collisions.
- Every finding is explained in plain language, not just a score: e.g. *"both skills claim
  the trigger phrase 'working with PDF files'"* — not just `score: 0.71`.
- Runs in milliseconds, zero ML dependencies, fully deterministic (fixes the dead
  `medium_overlap_threshold` bug from the coalescing logic as part of the rebuild — no
  legacy threshold semantics carry over).

**Tier 2 — opt-in, `--method llm`.**
Pairwise semantic judgment using the user's own Claude or OpenAI API key. Structured verdict
(conflict / adjacent / unrelated) with a one-sentence rationale. Cached by content hash so
repeat CI runs on unchanged skill pairs cost nothing.

**Quality gate for the engine itself:** a labeled eval set of skill-pair fixtures
(overlapping / adjacent / unrelated), checked into `tests/fixtures/conflict-eval/`, with a
CI check enforcing a precision/recall floor on Tier 1 so regressions are caught the same way
a linter's own tests would catch a broken rule.

## 6. `check` and verified bug fixes

`check --changed` remains the flagship command. Before anything else ships, fix the four
bugs verified by execution during review:

1. A modified non-skill file under the skills root (e.g. `skills/README.md`) must not crash
   the whole gate — `find_skill_root`/`_infer_deleted_root` needs a "not actually a skill
   file" path that's excluded, not force-treated as a broken skill root.
2. An `evals/` directory present without `config.yaml`/`evals.json` must not make the entire
   skill unparseable — parser should warn and continue, matching what `spec_validator`
   already assumes is possible.
3. `quality.py`'s `_RELATIVE_PATH_RE` character-class bug (`[^http]` meaning "not one of
   h/t/t/p" instead of "not starting with http") must be fixed so the broken-link blocker
   actually checks markdown links.
4. The dead `medium_overlap_threshold` (superseded by the Tier 1 rebuild in §5, but the
   general lesson — config knobs must have regression tests proving they affect output —
   applies to the new engine too).

**Output:** default TTY output renders findings inline (which checks failed, on which file,
which skill conflicts with which and why, the fix) using the existing Rich renderer already
used by `validate`/`secure`/`conflict` — `check`'s flat two-line markdown summary is
replaced, not kept as the default. `--format md`/`--format json` remain for CI consumption.

**`--against` default:** `conflict` gets the same implicit parent-directory default `check`
already has, and `check`'s default is stated explicitly in output (not silent).

**`fix` cannot generate a value that then passes a presence check.** If a fix would need a
placeholder (e.g. no author configured anywhere), it must leave the finding as a manual fix
required, not synthesize `author: TODO` and let it through.

## 7. GitHub Action

Ship `skill-guard-action@v1` as a first-class artifact (separate repo or `.github/actions/`
in this repo, decided at planning time): runs `check --changed` on the PR diff, posts one
PR comment with a summary table (skill, status, key findings), and emits inline annotations
on the specific lines/files. For the target team user, the Action is the front door; the CLI
is the local pre-push companion. The existing `.github/workflows/skill-guard-pr-gate.yml`
example becomes the Action's own dogfood workflow.

## 8. Testing strategy

Three legs, all enforced in CI:

1. **Anthropic-corpus regression.** A vendored (or git-submoduled) copy of a representative
   set of Anthropic's own public skills must pass `skill-guard check` cleanly. Any PR that
   tightens a default and breaks this fails CI. This is the direct fix for the review
   finding that Anthropic's own pdf skill currently scores 74/C with 3 blockers.
2. **Security rule false-positive tests.** Every rule in the new YAML ruleset (§3 security
   section) ships with at least one test asserting it does *not* fire on ordinary,
   benign shell/script content (the current suite has zero such tests, which is how
   `${VAR}` interpolation became a blocking finding).
3. **Conflict eval set** per §5.

Existing unit/integration suite (~120 tests) is kept and extended, not replaced.

## 9. Roadmap

**v0.9 — stop the bleeding** (small, fast, no new features):
- Scope cut (§3)
- Four verified bug fixes (§6)
- Dependency diet (§3)
- Default-severity flip: author/version → informational, description limit → 1024 (§4)
- Close the `fix`-inserts-TODO-that-passes hole (§6)
- README cleanup: duplicate Installation heading, stale `rev: v0.6.0` pre-commit pin,
  stale example output in `examples/README.md`, broken generated-config doc URL

**v1.0 — relaunch:**
- Rebuilt spec validator (§4)
- Tier 1 conflict engine + eval set (§5)
- Security rules moved to a data-driven YAML ruleset, FP-tested (§3, §8)
- Rich `check` output (§6)
- GitHub Action (§7)
- Rewritten README: honest comparison table vs skill-validator/skill-check, a short demo
  (asciinema or GIF) of the gate catching a real conflict on a PR
- Launch (Show HN / r/ClaudeAI / dev.to) only after the Anthropic-corpus test is green in CI

**v1.1+ (not designed yet, listed for context only):**
- LLM conflict tier (§5 Tier 2)
- SARIF output for GitHub Code Scanning
- Config presets (`strict` / `spec-only` / `team`)
- `skill-guard report`: repo-wide overlap matrix, stale-skill detection, trigger-space
  coverage — candidate second differentiator, not committed scope

## 10. Explicitly out of scope for v1

- Security scanning beyond a small, FP-tested, high-precision rule set (not a competitive
  differentiator — see §1)
- Live agent evaluation against a running endpoint
- Skill lifecycle management, hosted catalog, notifications
- Any feature whose primary user is "an org that already adopted skill-guard at scale"
  rather than "a team about to install it for the first time"
