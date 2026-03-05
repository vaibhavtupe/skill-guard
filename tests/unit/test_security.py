from pathlib import Path

from skill_gate.config import SecureConfig
from skill_gate.engine.security import run_security_scan
from skill_gate.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def test_security_malicious_skill():
    skill = parse_skill(FIXTURES / "malicious-skill")
    result = run_security_scan(skill, SecureConfig())
    assert result.passed is False
    assert result.critical_count >= 1
    assert result.high_count >= 1
