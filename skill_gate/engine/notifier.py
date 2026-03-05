"""Notification sinks for monitor reports."""

from __future__ import annotations

from typing import Any

import httpx

from skill_gate.models import MonitorReport


def send_slack_notification(webhook_url: str, report: MonitorReport) -> None:
    """Send a Slack notification when degraded/failing skills exist."""
    degraded_or_failing = [s for s in report.skills if (not s.healthy or s.stage == "degraded")]
    if not degraded_or_failing:
        return

    summary = (
        f"skill-gate monitor: {report.failing} failing, {report.degraded} degraded, "
        f"{report.healthy} healthy ({report.total_skills} total)"
    )
    fields = []
    for status in degraded_or_failing[:20]:
        findings = "; ".join(status.findings[:2]) if status.findings else "No findings provided"
        fields.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{status.skill_name}* ({status.stage})\n{findings}",
                },
            }
        )

    payload = {"text": summary, "blocks": fields}
    response = httpx.post(webhook_url, json=payload, timeout=15.0)
    response.raise_for_status()


def create_github_issue(token: str, repo: str, skill_name: str, findings: list[str]) -> str:
    """Create a skill-gate issue if one doesn't already exist for the skill."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    issue_title = f"skill-gate: {skill_name} health check failing"
    issues_url = f"https://api.github.com/repos/{repo}/issues"
    list_response = httpx.get(
        f"{issues_url}?state=open&labels=skill-gate",
        headers=headers,
        timeout=15.0,
    )
    list_response.raise_for_status()

    existing_issues: list[dict[str, Any]] = list_response.json()
    for issue in existing_issues:
        if issue.get("title") == issue_title:
            return str(issue.get("html_url", ""))

    if findings:
        body = "\n".join([f"- {finding}" for finding in findings])
    else:
        body = "- Health check failed with no detailed findings."

    create_response = httpx.post(
        issues_url,
        headers=headers,
        json={"title": issue_title, "body": body, "labels": ["skill-gate"]},
        timeout=15.0,
    )
    create_response.raise_for_status()
    payload = create_response.json()
    return str(payload.get("html_url", ""))
