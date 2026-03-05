from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from skill_guard.engine.notifier import create_github_issue, send_slack_notification
from skill_guard.models import MonitorReport, SkillHealthStatus


class _DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def _report(healthy: bool, stage: str = "production") -> MonitorReport:
    return MonitorReport(
        generated_at=datetime.now(UTC),
        total_skills=1,
        healthy=1 if healthy else 0,
        degraded=1 if stage == "degraded" else 0,
        failing=0 if healthy else 1,
        deprecated_skipped=0,
        run_time_seconds=1.2,
        skills=[
            SkillHealthStatus(
                skill_name="alpha",
                stage=stage,
                healthy=healthy,
                findings=["broken test"] if not healthy else [],
                transitioned=False,
            )
        ],
    )


def test_send_slack_notification_skips_when_all_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"value": False}

    def _post(*args, **kwargs):  # noqa: ANN002, ANN003
        called["value"] = True
        return _DummyResponse({})

    monkeypatch.setattr(httpx, "post", _post)
    send_slack_notification("https://hooks.slack.test", _report(healthy=True))
    assert called["value"] is False


def test_send_slack_notification_posts_when_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {"json": None}

    def _post(url: str, json: dict, timeout: float):  # noqa: A002
        captured["json"] = json
        assert url == "https://hooks.slack.test"
        assert timeout == 15.0
        return _DummyResponse({})

    monkeypatch.setattr(httpx, "post", _post)
    send_slack_notification("https://hooks.slack.test", _report(healthy=False))
    assert captured["json"] is not None
    assert "skill-gate monitor" in captured["json"]["text"]


def test_create_github_issue_returns_existing_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    def _get(url: str, headers: dict, timeout: float):
        assert "labels=skill-gate" in url
        assert headers["Authorization"].startswith("Bearer ")
        assert timeout == 15.0
        return _DummyResponse(
            [
                {
                    "title": "skill-gate: alpha health check failing",
                    "html_url": "https://github.com/org/repo/issues/10",
                }
            ]
        )

    def _post(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("POST should not be called when issue exists")

    monkeypatch.setattr(httpx, "get", _get)
    monkeypatch.setattr(httpx, "post", _post)
    issue_url = create_github_issue("token", "org/repo", "alpha", ["finding"])
    assert issue_url.endswith("/10")


def test_create_github_issue_creates_new_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    def _get(url: str, headers: dict, timeout: float):
        _ = (url, headers, timeout)
        return _DummyResponse([])

    def _post(url: str, headers: dict, json: dict, timeout: float):  # noqa: A002
        assert url.endswith("/issues")
        assert headers["Authorization"] == "Bearer token"
        assert json["title"] == "skill-gate: alpha health check failing"
        assert json["labels"] == ["skill-gate"]
        assert "- finding-a" in json["body"]
        assert timeout == 15.0
        return _DummyResponse({"html_url": "https://github.com/org/repo/issues/20"})

    monkeypatch.setattr(httpx, "get", _get)
    monkeypatch.setattr(httpx, "post", _post)
    issue_url = create_github_issue("token", "org/repo", "alpha", ["finding-a"])
    assert issue_url.endswith("/20")
