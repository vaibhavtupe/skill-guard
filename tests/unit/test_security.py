from pathlib import Path

from skill_guard.config import SecureConfig
from skill_guard.engine.security import run_security_scan
from skill_guard.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_security_malicious_skill():
    skill = parse_skill(FIXTURES / "malicious-skill")
    result = run_security_scan(skill, SecureConfig())
    assert result.passed is False
    assert result.critical_count >= 1
    assert result.high_count >= 1


def test_security_flags_external_urls_in_scripts_by_default() -> None:
    skill = parse_skill(FIXTURES / "malicious-skill")

    result = run_security_scan(skill, SecureConfig())

    assert any(f.id == "URL-001" for f in result.findings)


def test_security_allows_external_urls_when_enabled() -> None:
    skill = parse_skill(FIXTURES / "malicious-skill")

    result = run_security_scan(skill, SecureConfig(allow_external_urls_in_scripts=True))

    assert all(f.id != "URL-001" for f in result.findings)


def test_security_injection_fixture_detects_all_patterns() -> None:
    skill = parse_skill(FIXTURES / "injection-skill")
    result = run_security_scan(skill, SecureConfig())

    injection_ids = {finding.id for finding in result.findings if finding.category == "INJECTION"}
    for i in range(1, 9):
        assert f"INJECT-{i:03d}" in injection_ids


def test_security_skip_references_suppresses_reference_findings() -> None:
    skill = parse_skill(FIXTURES / "injection-skill")
    result = run_security_scan(skill, SecureConfig(skip_references=True))

    injection_ids = {finding.id for finding in result.findings if finding.category == "INJECTION"}
    assert "INJECT-003" not in injection_ids
    assert "INJECT-001" in injection_ids


def test_security_ignores_external_urls_in_comment_only_script(tmp_path: Path) -> None:
    skill_dir = tmp_path / "comment-url-skill"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: comment-url-skill\n"
            'description: "Use when checking whether comment-only URLs trigger false positives."\n'
            "---\n"
        ),
        encoding="utf-8",
    )
    (scripts_dir / "setup.sh").write_text(
        "# docs: https://example.com/install\necho ready\n",
        encoding="utf-8",
    )

    skill = parse_skill(skill_dir)
    result = run_security_scan(skill, SecureConfig())

    assert all(f.id != "URL-001" for f in result.findings)
