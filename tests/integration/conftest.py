from __future__ import annotations

import pytest
from fastapi import FastAPI


@pytest.fixture
def mock_agent() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/responses")
    async def responses(payload: dict) -> dict:
        prompt = str(payload.get("input", ""))
        tool_name = "valid-skill" if "diagnose" in prompt.lower() else "other-skill"
        return {
            "output": [
                {"type": "tool_call", "name": tool_name},
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "mock response from integration fixture"}
                    ],
                },
            ]
        }

    return app
