"""Shared trust-state semantics for command outputs."""

from __future__ import annotations

from typing import Literal

from skill_guard.models import (
    AgentTestComparisonResult,
    AgentTestResult,
    CheckRunReport,
    CheckSkillReport,
    ConflictResult,
    SecurityResult,
    ValidationResult,
)

TrustState = Literal["clean", "warning", "exception", "needs_review", "blocking"]


def validation_trust_state(result: ValidationResult) -> TrustState:
    if result.blockers > 0:
        return "blocking"
    if result.warnings > 0:
        return "warning"
    return "clean"


def security_trust_state(result: SecurityResult) -> TrustState:
    unsuppressed = [finding for finding in result.findings if not finding.suppressed]
    suppressed = [finding for finding in result.findings if finding.suppressed]
    if unsuppressed and not result.passed:
        return "blocking"
    if suppressed:
        return "exception"
    if unsuppressed:
        return "warning"
    return "clean"


def conflict_trust_state(result: ConflictResult) -> TrustState:
    if result.name_collision or result.high_conflicts > 0:
        return "blocking"
    if result.medium_conflicts > 0:
        return "warning"
    return "clean"


def test_trust_state(result: AgentTestResult | AgentTestComparisonResult) -> TrustState:
    test_result = result.with_skill if isinstance(result, AgentTestComparisonResult) else result
    if not test_result.passed:
        return "blocking"
    if any(test.needs_review for test in test_result.results):
        return "needs_review"
    return "clean"


def check_skill_trust_state(skill: CheckSkillReport) -> TrustState:
    if skill.status == "failed":
        return "blocking"

    security = skill.result.get("security") or {}
    findings = security.get("findings") or []
    if findings and any(finding.get("suppressed") for finding in findings):
        return "exception"

    test_result = skill.result.get("test") or {}
    if any(test.get("needs_review") for test in test_result.get("results", [])):
        return "needs_review"

    if skill.validation == "warning" or skill.conflict == "warning" or skill.test == "warning":
        return "warning"

    return "clean"


def check_run_trust_state(report: CheckRunReport) -> TrustState:
    states = [check_skill_trust_state(skill) for skill in report.skills]
    if not states:
        return "clean"
    return max(states, key=_trust_state_rank)


def trust_state_label(state: TrustState) -> str:
    return {
        "clean": "clean",
        "warning": "warning",
        "exception": "intentional exception",
        "needs_review": "needs review",
        "blocking": "blocking",
    }[state]


def _trust_state_rank(state: TrustState) -> int:
    return {
        "clean": 0,
        "warning": 1,
        "exception": 2,
        "needs_review": 3,
        "blocking": 4,
    }[state]
