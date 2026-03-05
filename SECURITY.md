# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 0.4.x | ✅ |
| < 0.4 | ❌ |

## Reporting a Vulnerability

**Please do not report security vulnerabilities via public GitHub issues.**

Report vulnerabilities privately via [GitHub Security Advisories](https://github.com/vaibhavtupe/skill-guard/security/advisories/new).

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix (optional)

You will receive a response within **48 hours** and a fix within **7 days** for critical issues.

## Scope

Security issues in scope:
- Prompt injection bypass in the `secure` scanner
- Path traversal in skill parsing
- Command injection via hook scripts
- Credential leakage in output/logs

Out of scope:
- Issues in optional dependencies (report upstream)
- Denial of service via large skill files
