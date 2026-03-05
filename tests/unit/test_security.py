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
