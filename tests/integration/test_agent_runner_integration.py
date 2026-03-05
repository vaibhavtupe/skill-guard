"""Integration tests: agent_runner against a mock FastAPI Responses API server."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request

from skill_gate.config import TestConfig
from skill_gate.engine.agent_runner import run_agent_tests, wait_for_agent_ready
from skill_gate.models import HookError

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


# ---------------------------------------------------------------------------
# Shared live server fixture
# ---------------------------------------------------------------------------

def _build_mock_app() -> FastAPI:
    """Build the mock Responses API app."""
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/responses")
    async def responses(request: Request) -> dict:
        payload = await request.json()
        prompt = str(payload.get("input", ""))

        if "dropping packets" in prompt:
            return {
                "output": [
                    {"type": "tool_call", "name": "valid-skill"},
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "diagnostic latency detected on route"}
                        ],
                    },
                ]
            }

        if "0.01% packet loss" in prompt:
            return {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "no active connections found"}
                        ],
                    }
                ]
            }

        # not-my-job: out-of-scope prompt → polite refusal, no skill/diagnostic terms
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "That request is outside my scope. Please contact Azure support.",
                        }
                    ],
                }
            ]
        }

    return app


class _LiveServer:
    """Tiny wrapper that spins up uvicorn in a background thread."""

    def __init__(self, app: FastAPI, host: str = "127.0.0.1", port: int = 0) -> None:
        self._app = app
        self._host = host
        self._port = port
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self.base_url: str = ""

    def start(self) -> None:
        import socket

        # bind to a free port
        with socket.socket() as s:
            s.bind((self._host, 0))
            self._port = s.getsockname()[1]

        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
            log_level="error",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        self._wait_ready()
        self.base_url = f"http://{self._host}:{self._port}"

    def _wait_ready(self, timeout: float = 5.0) -> None:
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                resp = httpx.get(
                    f"http://{self._host}:{self._port}/health", timeout=1.0
                )
                if resp.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        raise RuntimeError("Live server did not become ready in time")

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=3)


@pytest.fixture(scope="module")
def live_server():
    srv = _LiveServer(_build_mock_app())
    srv.start()
    yield srv
    srv.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_full_eval_suite_passes_against_live_server(live_server: _LiveServer) -> None:
    """All three evals in valid-skill pass when the mock agent returns correct responses."""
    skill_path = FIXTURES / "valid-skill"
    config = TestConfig(endpoint=live_server.base_url, model="mock-model")

    result = asyncio.run(run_agent_tests(
        __import__("skill_gate.parser", fromlist=["parse_skill"]).parse_skill(skill_path),
        config,
    ))

    assert result.total_tests == 3
    assert result.passed_tests == 3
    assert result.pass_rate == 1.0
    assert result.passed is True


@pytest.mark.integration
def test_skill_triggered_check_via_live_server(live_server: _LiveServer) -> None:
    """skill_triggered expectation resolves correctly when tool_call name matches."""
    from skill_gate.parser import parse_skill

    skill = parse_skill(FIXTURES / "valid-skill")
    # Limit to first test and add skill_triggered expectation
    first = skill.evals_config.tests[0]
    first.expect.skill_triggered = "valid-skill"
    skill.evals_config.tests = [first]

    config = TestConfig(endpoint=live_server.base_url, model="mock-model")
    result = asyncio.run(run_agent_tests(skill, config))

    assert result.results[0].passed is True
    assert "skill_triggered:valid-skill" in result.results[0].checks_passed


@pytest.mark.integration
def test_not_contains_check_blocks_out_of_scope_response(live_server: _LiveServer) -> None:
    """not-my-job eval: response must not contain diagnostic/packet keywords."""
    from skill_gate.parser import parse_skill

    skill = parse_skill(FIXTURES / "valid-skill")
    not_my_job = skill.evals_config.tests[2]  # "not-my-job"
    skill.evals_config.tests = [not_my_job]

    config = TestConfig(endpoint=live_server.base_url, model="mock-model")
    result = asyncio.run(run_agent_tests(skill, config))

    assert result.results[0].passed is True
    for check in result.results[0].checks_passed:
        assert check.startswith("not_contains:")


@pytest.mark.integration
def test_health_check_passes_for_live_server(live_server: _LiveServer) -> None:
    """wait_for_agent_ready should succeed immediately against the live server."""
    asyncio.run(
        wait_for_agent_ready(live_server.base_url, api_key=None, timeout_seconds=3)
    )


@pytest.mark.integration
def test_eval_fails_when_expected_text_missing(live_server: _LiveServer) -> None:
    """Inject an impossible contains expectation; test should fail with checks_failed populated."""
    from skill_gate.parser import parse_skill

    skill = parse_skill(FIXTURES / "valid-skill")
    first = skill.evals_config.tests[0]
    first.expect.contains = ["diagnostic", "THIS_WILL_NEVER_APPEAR_XYZ"]
    skill.evals_config.tests = [first]

    config = TestConfig(endpoint=live_server.base_url, model="mock-model")
    result = asyncio.run(run_agent_tests(skill, config))

    assert result.results[0].passed is False
    assert "contains:THIS_WILL_NEVER_APPEAR_XYZ" in result.results[0].checks_failed


@pytest.mark.integration
def test_no_evals_raises_hook_error(live_server: _LiveServer) -> None:
    """Skills without evals should raise HookError, not crash silently."""
    from skill_gate.parser import parse_skill

    skill = parse_skill(FIXTURES / "valid-skill")
    skill.evals_config = None  # simulate missing evals

    config = TestConfig(endpoint=live_server.base_url, model="mock-model")
    with pytest.raises(HookError, match="No eval tests found"):
        asyncio.run(run_agent_tests(skill, config))
