"""JSON output formatter."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from skill_guard.models import (
    AgentTestComparisonResult,
    AgentTestResult,
    CheckRunReport,
    ConflictResult,
    SecurityResult,
    ValidationResult,
)
from skill_guard.output.semantics import (
    check_run_trust_state,
    check_skill_trust_state,
    conflict_trust_state,
    security_trust_state,
    test_trust_state,
    validation_trust_state,
)


def format_as_json(result: Any, command: str | None = None) -> str:
    payload = {
        "command": command,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    if isinstance(result, BaseModel):
        payload["result"] = _serialize_with_trust_state(result)
    else:
        payload["result"] = result

    return json.dumps(payload, indent=2, default=str)


def _serialize_with_trust_state(result: BaseModel) -> dict[str, Any]:
    payload = result.model_dump(mode="json")

    if isinstance(result, ValidationResult):
        payload["trust_state"] = validation_trust_state(result)
    elif isinstance(result, SecurityResult):
        payload["trust_state"] = security_trust_state(result)
    elif isinstance(result, ConflictResult):
        payload["trust_state"] = conflict_trust_state(result)
    elif isinstance(result, AgentTestResult | AgentTestComparisonResult):
        payload["trust_state"] = test_trust_state(result)
    elif isinstance(result, CheckRunReport):
        payload["trust_state"] = check_run_trust_state(result)
        for dumped_skill, skill in zip(payload["skills"], result.skills, strict=False):
            dumped_skill["trust_state"] = check_skill_trust_state(skill)

    return payload
