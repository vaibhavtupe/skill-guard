## Issue #107 plan

### Root cause

`no_broken_body_paths` scans plain text with a broad regex that matches any dotted token ending in a 2-5 character segment. That incorrectly treats API field references such as `reader.pages` or `response.output_text` as relative file paths.

### Proposed change

Keep markdown-link and inline-code path validation as-is, but narrow plain-text path detection to explicit relative paths:

- paths with a directory separator like `references/runbook.md`
- paths starting with `./` or `../`
- standalone document-style filenames with an uppercase basename like `REFERENCE.md`

This preserves broken-link detection for real body references while avoiding dotted API/member references and example filenames that are not repo-relative paths.
