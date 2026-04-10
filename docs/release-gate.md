# Release Gate Checklist

Use this checklist before creating a tag or publishing a release.

This checklist operationalizes the policy in `docs/automation-policy.md` and the scoped release definition in `ROADMAP.md`.

## 1) Scope Confirmation
- [ ] The target version exists in `ROADMAP.md`
- [ ] Every issue included in the release maps to that roadmap section
- [ ] No major shipped behavior is outside roadmap scope without an explicit roadmap update
- [ ] Out-of-scope features are not represented as shipped scope

## 2) Tests and Validation
- [ ] Required automated tests are green
- [ ] New behavior has tests where appropriate
- [ ] If tests were intentionally not added, the PR/release notes explain why
- [ ] Manual verification steps for docs/process-only changes are recorded

## 3) Spec Compliance
- [ ] README claims match shipped behavior
- [ ] CLI help text matches actual commands/options
- [ ] `docs/configuration-reference.md` matches config parsing and defaults
- [ ] Eval docs match parser/runtime behavior
- [ ] Any experimental or partial feature is clearly labeled as such

## 4) CI and Workflow Integrity
- [ ] The documented primary CI workflow still works as written
- [ ] Exit codes and output contracts match docs
- [ ] Aggregate reporting/artifacts are consistent with the current implementation
- [ ] Release does not depend on undocumented shell glue in the primary workflow

## 5) User Trust Check
- [ ] No placeholder features are presented as production-ready
- [ ] Known false-positive-prone checks are documented or mitigated
- [ ] Remediation guidance is accurate and actionable
- [ ] Product positioning still matches what the release actually delivers

## 6) Release Readiness
- [ ] `CHANGELOG.md` reflects user-visible changes
- [ ] Version bump matches the release scope
- [ ] Tag/release notes describe shipped behavior, not aspirational future work
- [ ] Final release reviewer confirms `ROADMAP.md` still matches shipped reality

## Evidence to attach to release PR or tag prep
- test command output
- spec-compliance review notes
- any manual verification notes
- links to milestone/issues included in the release
