# ROADMAP.md

`ROADMAP.md` is the canonical scope source for this repo.

If README, config docs, CLI help, GitHub issues, or shipped behavior conflict with this file, update `ROADMAP.md` first and then reconcile the rest of the repo.

## Current Product Focus

See [docs/superpowers/specs/2026-08-05-v1-relaunch-design.md](docs/superpowers/specs/2026-08-05-v1-relaunch-design.md) for the full positioning, architecture, and roadmap through v1.1+.

**v0.9.0 theme:** Stop the bleeding — no new features. Cut the codebase to the repo-aware PR-gate core, fix four verified correctness bugs, flip defaults so a clean Anthropic-style skill passes the gate, stop `fix` from fabricating placeholder metadata, and remove the ~184MB scikit-learn dependency. See the design doc, section 9, for the full scope.

**v1.0.0 theme (next, not yet started):** Relaunch as "the PR gate for your team's Agent Skills repo." Rebuild the spec validator against the real agentskills.io constraints, replace the conflict engine with an explainable Tier-1 lexical engine plus an optional LLM tier, move security rules to a data-driven, false-positive-tested YAML ruleset, redesign `check`'s default output to show findings inline, and ship a first-class GitHub Action. See the design doc, sections 4-9.

## Release Gate

A version may be tagged only when all of the following are true:

- Tests required by the scoped issues are green
- README/docs/config/CLI help match shipped behavior
- Experimental or partial features are clearly labeled
- Roadmap scope still matches what is actually shipping
- Release checklist in `docs/release-gate.md` is completed

## Next Release Planning Rules

For future releases:

1. Add the new version section here first
2. Map every planned GitHub issue to the version section
3. Define explicit in-scope and out-of-scope items
4. Update the release gate if shipping criteria changed
5. Do not treat README as the planning source of truth
