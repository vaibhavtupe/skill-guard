# ROADMAP.md

`ROADMAP.md` is the canonical scope source for this repo.

If README, config docs, CLI help, GitHub issues, or shipped behavior conflict with this file, update `ROADMAP.md` first and then reconcile the rest of the repo.

## Current Product Focus

**v0.8.0 theme:** Make `skill-guard` the default pre-merge gate for shared skill repos.

The wedge for this release is not broad lifecycle governance. It is a reliable, repo-native, PR-native quality gate that teams can install quickly and trust in CI.

## Release Gate

A version may be tagged only when all of the following are true:

- Tests required by the scoped issues are green
- README/docs/config/CLI help match shipped behavior
- Experimental or partial features are clearly labeled
- Roadmap scope still matches what is actually shipping
- Release checklist in `docs/release-gate.md` is completed

## v0.8.0 — Default PR Gate

### Goal

Make `skill-guard` feel like the obvious CI gate for shared Agent Skills repositories:

- repo-aware instead of single-skill-only
- PR-aware instead of shell-glue-driven
- strong offline-first value by default
- clear, trustworthy docs and release criteria

### In Scope

#### #109 — Repo-level changed-skill detection and multi-skill PR check flow
- Add first-class changed-skill detection
- Support multi-skill PR evaluation in `check`
- Aggregate per-skill results into one run summary
- Handle zero-change, rename, and delete scenarios cleanly

#### #110 — Official GitHub Actions workflow and PR-native output contract
- Ship one canonical CI path for pull requests
- Support aggregate JSON and human-readable markdown summaries
- Remove brittle primary docs examples that only check one changed skill
- Document artifact/reporting expectations clearly

#### #111 — Simplify CLI positioning around `check` as the default workflow
- Make `check` the primary recommended command
- Reduce first-run cognitive load in CLI help and docs
- Clearly separate advanced/secondary workflows from the default path

#### #112 — Remove spec drift and clearly mark placeholder or experimental features
- Align README, config docs, parser behavior, and command reality
- Remove or explicitly mark incomplete/experimental features
- Fix mismatches that erode user trust

#### #113 — Improve offline-first remediation and reduce false-positive friction
- Improve actionable remediation in validate/secure/conflict output
- Tighten noisy checks where recent false positives surfaced
- Make blocker vs warning behavior clearer

#### #114 — Harden live eval workflow for deterministic CI usage
- Define one recommended CI eval path
- Make setup failures and artifacts easier to diagnose
- De-emphasize non-default eval/injection complexity in the primary workflow

#### #115 — Add `ROADMAP.md` and release-gate spec compliance checklist
- Create a canonical roadmap file
- Add an operational release/spec-compliance checklist
- Tie repo process docs to roadmap-as-spec

### Out of Scope for v0.8.0

The following may remain present in the repo, but are not release-defining for v0.8.0:

- expanded lifecycle automation
- hosted governance workflows
- notification expansion
- catalog as a primary product pillar
- advanced conflict modes that are not production-ready

## Definition of Done for v0.8.0

v0.8.0 is done only when:

- multi-skill PR flow works end to end
- the official GitHub Actions path is documented and credible
- static/offline mode is useful without live eval setup
- docs and config references match actual behavior
- release-gate checklist is completed before tagging

## Next Release Planning Rules

For future releases:

1. Add the new version section here first
2. Map every planned GitHub issue to the version section
3. Define explicit in-scope and out-of-scope items
4. Update the release gate if shipping criteria changed
5. Do not treat README as the planning source of truth
