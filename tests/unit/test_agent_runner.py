from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from skill_guard.config import TestConfig as RunnerConfig
from skill_guard.engine import agent_runner
from skill_guard.engine.agent_runner import run_agent_tests, run_hook, wait_for_agent_ready
from skill_guard.models import HookError
from skill_guard.parser import parse_skill

FIXTURES = Path(__file__).parent.parent / "fixtures" / "skills"


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    class PatchedAsyncClient(real_async_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(agent_runner.httpx, "AsyncClient", PatchedAsyncClient)


@pytest.mark.asyncio
async def test_run_agent_tests_against_mock_responses_api(monkeypatch: pytest.MonkeyPatch) -> None:
    skill = parse_skill(FIXTURES / "valid-skill")

    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read().decode("utf-8")
        if "dropping packets" in payload:
            body = {
                "output": [
                    {"type": "tool_call", "name": "valid-skill"},
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "diagnostic latency"}],
                    },
                ]
            }
        elif "0.01% packet loss" in payload:
            body = {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "no active connections found"}],
                    }
                ]
            }
        else:
            body = {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Cannot help with Azure."}],
                    }
                ]
            }
        return httpx.Response(200, json=body)

    _patch_async_client(monkeypatch, handler)
    config = RunnerConfig(endpoint="https://mock-agent.test", model="gpt-4.1-mini")
    result = await run_agent_tests(skill, config)

    assert result.total_tests == 3
    assert result.results[0].tool_calls == ["valid-skill"]
    assert result.results[0].passed is True


@pytest.mark.asyncio
async def test_skill_triggered_check_passes_on_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    skill = parse_skill(FIXTURES / "valid-skill")
    skill.evals_config.tests = [skill.evals_config.tests[0]]
    skill.evals_config.tests[0].expect.skill_triggered = "valid-skill"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": [
                    {"type": "tool_call", "name": "valid-skill"},
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "diagnostic latency"}],
                    },
                ]
            },
        )

    _patch_async_client(monkeypatch, handler)
    result = await run_agent_tests(
        skill, RunnerConfig(endpoint="https://mock-agent.test", model="gpt-4.1")
    )

    assert result.results[0].passed is True
    assert "skill_triggered:valid-skill" in result.results[0].checks_passed


@pytest.mark.asyncio
async def test_contains_check_passes_and_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    skill = parse_skill(FIXTURES / "valid-skill")
    first = skill.evals_config.tests[0]
    first.expect.contains = ["diagnostic", "missing-term"]
    skill.evals_config.tests = [first]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "diagnostic ok"}],
                    }
                ]
            },
        )

    _patch_async_client(monkeypatch, handler)
    result = await run_agent_tests(
        skill, RunnerConfig(endpoint="https://mock-agent.test", model="gpt-4.1")
    )

    assert "contains:diagnostic" in result.results[0].checks_passed
    assert "contains:missing-term" in result.results[0].checks_failed
    assert result.results[0].passed is False


@pytest.mark.asyncio
async def test_latency_check_uses_max_latency_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    skill = parse_skill(FIXTURES / "valid-skill")
    first = skill.evals_config.tests[0]
    first.expect.max_latency_ms = 150
    first.expect.contains = ["diagnostic"]
    skill.evals_config.tests = [first]

    perf_values = iter([0.0, 0.10, 0.30, 0.40, 0.50, 0.60, 0.70])

    def fake_perf_counter() -> float:
        try:
            return next(perf_values)
        except StopIteration:
            return 0.70

    monkeypatch.setattr(agent_runner.time, "perf_counter", fake_perf_counter)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": "diagnostic"}]}
                ]
            },
        )

    _patch_async_client(monkeypatch, handler)
    result = await run_agent_tests(
        skill, RunnerConfig(endpoint="https://mock-agent.test", model="gpt-4.1")
    )

    assert "max_latency_ms:150" in result.results[0].checks_failed
    assert result.results[0].passed is False


def test_run_hook_success(tmp_path: Path) -> None:
    hook = tmp_path / "hook.sh"
    hook.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    hook.chmod(0o755)
    run_hook(hook, tmp_path, "https://agent.test")


def test_run_hook_failure_raises(tmp_path: Path) -> None:
    hook = tmp_path / "hook_fail.sh"
    hook.write_text("#!/usr/bin/env sh\necho boom >&2\nexit 2\n", encoding="utf-8")
    hook.chmod(0o755)
    with pytest.raises(HookError):
        run_hook(hook, tmp_path, "https://agent.test")


@pytest.mark.asyncio
async def test_wait_for_agent_ready_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 2:
            return httpx.Response(503)
        return httpx.Response(200)

    _patch_async_client(monkeypatch, handler)
    await wait_for_agent_ready("https://mock-agent.test", "key", timeout_seconds=3)


@pytest.mark.asyncio
async def test_wait_for_agent_ready_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    _patch_async_client(monkeypatch, handler)
    with pytest.raises(HookError):
        await wait_for_agent_ready("https://mock-agent.test", None, timeout_seconds=0)
