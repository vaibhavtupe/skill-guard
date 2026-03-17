"""Agent integration test runner (Phase 2)."""

from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from skill_guard.config import TestConfig
from skill_guard.engine.test_injection import TestInjectionContext
from skill_guard.models import (
    AgentTestResult,
    EvalExpectation,
    EvalTestResult,
    HealthCheckTimeoutError,
    HookError,
    ParsedSkill,
)


def run_hook(hook_script: Path, skill_path: Path, endpoint: str) -> None:
    """Run a pre/post test hook script."""
    proc = subprocess.run(
        [str(hook_script), str(skill_path), endpoint],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        details = stderr or stdout or "No output."
        raise HookError(f"Hook failed ({hook_script}) with exit code {proc.returncode}: {details}")


async def wait_for_agent_ready(
    endpoint: str,
    api_key: str | None,
    timeout_seconds: int,
    health_check_path: str = "/health",
) -> None:
    """Poll endpoint health until ready or timeout."""
    health_url = urljoin(f"{endpoint.rstrip('/')}/", health_check_path.lstrip("/"))
    headers = _build_headers(api_key)
    deadline = time.monotonic() + timeout_seconds

    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.monotonic() < deadline:
            try:
                resp = await client.get(health_url, headers=headers)
                if resp.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)

    raise HealthCheckTimeoutError(
        f"Timed out waiting for agent health at '{health_url}' after {timeout_seconds}s"
    )


async def run_agent_tests(skill: ParsedSkill, config: TestConfig) -> AgentTestResult:
    """Execute eval tests against an agent endpoint using the OpenAI Responses API."""
    if not config.endpoint:
        raise HookError("Agent endpoint is required. Set test.endpoint or pass --endpoint.")
    if not skill.evals_config or not skill.evals_config.tests:
        raise HookError(f"No eval tests found for skill '{skill.metadata.name}'.")

    endpoint = config.endpoint.rstrip("/")
    responses_url = f"{endpoint}/v1/responses"

    injection_context = TestInjectionContext(skill=skill, config=config)

    started = time.perf_counter()
    results: list[EvalTestResult] = []

    headers = _build_headers(config.api_key)

    try:
        injection_context.run_pre()
        if config.reload_command:
            _run_reload_command(config.reload_command)
            if config.reload_wait_seconds > 0:
                await asyncio.sleep(config.reload_wait_seconds)
        if (
            config.reload_command
            or config.injection.method != "custom_hook"
            or config.injection.pre_test_hook
        ):
            await wait_for_agent_ready(
                endpoint,
                config.api_key,
                config.reload_timeout_seconds,
                config.reload_health_check_path,
            )

        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            for test in skill.evals_config.tests:
                prompt_path = skill.path / "evals" / test.prompt_file
                prompt_text = prompt_path.read_text(encoding="utf-8")

                payload: dict[str, Any] = {"model": config.model, "input": prompt_text}
                request_started = time.perf_counter()
                response = await client.post(responses_url, headers=headers, json=payload)
                latency_ms = int((time.perf_counter() - request_started) * 1000)

                response.raise_for_status()
                body = response.json()
                response_text, tool_calls = _extract_response_data(body)
                checks_passed, checks_failed = _evaluate_checks(
                    response_text=response_text,
                    tool_calls=tool_calls,
                    latency_ms=latency_ms,
                    test_expect=test.expect,
                )

                skill_triggered = None
                if test.expect.skill_triggered and test.expect.skill_triggered in tool_calls:
                    skill_triggered = test.expect.skill_triggered

                results.append(
                    EvalTestResult(
                        test_name=test.name,
                        passed=not checks_failed,
                        prompt=prompt_text,
                        response_text=response_text,
                        latency_ms=latency_ms,
                        checks_passed=checks_passed,
                        checks_failed=checks_failed,
                        skill_triggered=skill_triggered,
                        tool_calls=tool_calls,
                    )
                )
    finally:
        injection_context.run_post()

    total_time = time.perf_counter() - started
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r.passed)
    failed_tests = total_tests - passed_tests
    pass_rate = (passed_tests / total_tests) if total_tests else 0.0
    avg_latency_ms = (sum(r.latency_ms for r in results) / total_tests) if total_tests else 0.0

    return AgentTestResult(
        skill_name=skill.metadata.name,
        endpoint=endpoint,
        total_tests=total_tests,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        pass_rate=pass_rate,
        results=results,
        total_time_seconds=total_time,
        avg_latency_ms=avg_latency_ms,
        passed=failed_tests == 0,
    )


def _run_reload_command(command: str) -> None:
    proc = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        details = stderr or stdout or "No output."
        raise HookError(f"Reload command failed with exit code {proc.returncode}: {details}")


def _extract_response_data(response_body: dict[str, Any]) -> tuple[str, list[str]]:
    output_items = response_body.get("output", []) or []
    text_parts: list[str] = []
    tool_calls: list[str] = []

    for item in output_items:
        if item.get("type") == "message":
            text_parts.extend(_message_text_parts(item))
        if item.get("type") == "tool_call":
            name = item.get("name") or item.get("tool_name")
            if not name and isinstance(item.get("function"), dict):
                name = item["function"].get("name")
            if name:
                tool_calls.append(str(name))

    return "\n".join(part for part in text_parts if part).strip(), tool_calls


def _message_text_parts(item: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    content = item.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type in {"output_text", "text"} and block.get("text"):
                parts.append(str(block["text"]))
    if item.get("text"):
        parts.append(str(item["text"]))
    return parts


def _evaluate_checks(
    response_text: str,
    tool_calls: list[str],
    latency_ms: int,
    test_expect: EvalExpectation,
) -> tuple[list[str], list[str]]:
    checks_passed: list[str] = []
    checks_failed: list[str] = []

    for expected in test_expect.contains:
        if expected in response_text:
            checks_passed.append(f"contains:{expected}")
        else:
            checks_failed.append(f"contains:{expected}")

    for forbidden in test_expect.not_contains:
        if forbidden in response_text:
            checks_failed.append(f"not_contains:{forbidden}")
        else:
            checks_passed.append(f"not_contains:{forbidden}")

    if test_expect.min_length is not None:
        if len(response_text) >= test_expect.min_length:
            checks_passed.append(f"min_length:{test_expect.min_length}")
        else:
            checks_failed.append(f"min_length:{test_expect.min_length}")

    if test_expect.max_latency_ms is not None:
        if latency_ms <= test_expect.max_latency_ms:
            checks_passed.append(f"max_latency_ms:{test_expect.max_latency_ms}")
        else:
            checks_failed.append(f"max_latency_ms:{test_expect.max_latency_ms}")

    if test_expect.skill_triggered:
        if test_expect.skill_triggered in tool_calls:
            checks_passed.append(f"skill_triggered:{test_expect.skill_triggered}")
        else:
            checks_failed.append(f"skill_triggered:{test_expect.skill_triggered}")

    if test_expect.skill_not_triggered:
        if test_expect.skill_not_triggered in tool_calls:
            checks_failed.append(f"skill_not_triggered:{test_expect.skill_not_triggered}")
        else:
            checks_passed.append(f"skill_not_triggered:{test_expect.skill_not_triggered}")

    return checks_passed, checks_failed


def _build_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers
