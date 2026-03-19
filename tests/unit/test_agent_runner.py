from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from skill_guard.config import TestConfig as RunnerConfig
from skill_guard.engine import agent_runner
from skill_guard.engine.agent_runner import run_agent_tests, run_hook, wait_for_agent_ready
from skill_guard.models import AgentTestResult, HealthCheckTimeoutError, HookError
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
async def test_run_agent_tests_with_baseline_computes_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill = parse_skill(FIXTURES / "valid-skill")

    async def fake_run_agent_tests(  # noqa: ARG001
        skill_arg,
        config,
        *,
        inject_skill=True,
        write_workspace=True,
    ):
        passed_tests = 2 if inject_skill else 1
        total_tests = 2
        return AgentTestResult(
            skill_name=skill_arg.metadata.name,
            endpoint="https://mock-agent.test",
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=total_tests - passed_tests,
            pass_rate=passed_tests / total_tests,
            results=[],
            total_time_seconds=0.1,
            avg_latency_ms=10.0,
            passed=passed_tests == total_tests,
        )

    monkeypatch.setattr(agent_runner, "run_agent_tests", fake_run_agent_tests)
    result = await agent_runner.run_agent_tests_with_baseline(
        skill, RunnerConfig(endpoint="https://mock-agent.test", model="gpt-4.1")
    )

    assert result.pass_rate_delta == 0.5
    assert result.passed_tests_delta == 1


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
    with pytest.raises(HealthCheckTimeoutError):
        await wait_for_agent_ready("https://mock-agent.test", None, timeout_seconds=0)


@pytest.mark.asyncio
async def test_wait_for_agent_ready_uses_custom_health_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = {"path": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200)

    _patch_async_client(monkeypatch, handler)
    await wait_for_agent_ready(
        "https://mock-agent.test",
        None,
        timeout_seconds=1,
        health_check_path="/readyz",
    )

    assert seen["path"] == "/readyz"


@pytest.mark.asyncio
async def test_run_agent_tests_runs_post_hook_after_pre_hook_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill = parse_skill(FIXTURES / "valid-skill")
    calls: list[tuple[str, str]] = []

    def fake_run_hook(hook_script: Path, skill_path: Path, endpoint: str) -> None:
        calls.append((hook_script.name, endpoint))
        if hook_script.name == "pre.sh":
            raise HookError("pre hook failed")

    monkeypatch.setattr(agent_runner, "run_hook", fake_run_hook)

    config = RunnerConfig(
        endpoint="https://mock-agent.test",
        model="gpt-4.1",
        injection={
            "pre_test_hook": str(skill.path / "pre.sh"),
            "post_test_hook": str(skill.path / "post.sh"),
        },
    )

    with pytest.raises(HookError, match="pre hook failed"):
        await run_agent_tests(skill, config)

    assert calls == [("pre.sh", "https://mock-agent.test"), ("post.sh", "https://mock-agent.test")]


@pytest.mark.asyncio
async def test_run_agent_tests_runs_reload_command_and_waits_for_custom_health_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill = parse_skill(FIXTURES / "valid-skill")
    calls: list[str] = []

    def fake_reload_command(command: str) -> None:
        calls.append(f"reload:{command}")

    async def fake_wait_for_agent_ready(
        endpoint: str, api_key, timeout_seconds: int, health_check_path: str = "/health"
    ) -> None:  # noqa: ANN001
        calls.append(f"health:{endpoint}:{timeout_seconds}:{health_check_path}")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "diagnostic latency"}],
                    }
                ]
            },
        )

    _patch_async_client(monkeypatch, handler)
    monkeypatch.setattr(agent_runner, "_run_reload_command", fake_reload_command)
    monkeypatch.setattr(agent_runner, "wait_for_agent_ready", fake_wait_for_agent_ready)

    sleep_calls: list[int] = []

    async def fake_sleep(seconds: int) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(agent_runner.asyncio, "sleep", fake_sleep)

    config = RunnerConfig(
        endpoint="https://mock-agent.test",
        model="gpt-4.1",
        reload_command="echo reload",
        reload_wait_seconds=2,
        reload_health_check_path="/readyz",
    )
    await run_agent_tests(skill, config)

    assert calls[0] == "reload:echo reload"
    assert calls[1] == "health:https://mock-agent.test:60:/readyz"
    assert sleep_calls == [2]
