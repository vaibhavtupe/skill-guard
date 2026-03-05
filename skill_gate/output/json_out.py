"""JSON output formatter."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel


def format_as_json(result: Any, command: str | None = None) -> str:
    payload = {
        "command": command,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if isinstance(result, BaseModel):
        payload["result"] = result.model_dump(mode="json")
    else:
        payload["result"] = result

    return json.dumps(payload, indent=2, default=str)
