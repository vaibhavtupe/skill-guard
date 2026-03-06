"""CLI command: skill-guard monitor."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import typer
from ruamel.yaml import YAML

from skill_guard.config import ConfigError, TestConfig, load_config
from skill_guard.engine.agent_runner import run_agent_tests
from skill_guard.engine.catalog_manager import CatalogManager
from skill_guard.engine.lifecycle import apply_stage_transitions, check_ownership, check_staleness
from skill_guard.engine.notifier import create_github_issue, send_slack_notification
from skill_guard.engine.quality import run_validation
from skill_guard.engine.security import run_security_scan
from skill_guard.engine.similarity import compute_similarity
from skill_guard.models import Catalog, MonitorReport, SkillHealthStatus, SkillParseError
from skill_guard.output.html import format_as_html
from skill_guard.output.json_out import format_as_json
from skill_guard.parser import parse_skill

CATALOG_OPT = typer.Option(..., "--catalog", help="Path to skill catalog YAML")
ENDPOINT_OPT = typer.Option(None, "--endpoint", help="Agent endpoint URL")
STATIC_ONLY_OPT = typer.Option(
    False,
    "--static-only",
    help="Run only static checks (validate, secure, conflict), skip agent tests.",
)
CONFIG_OPT = typer.Option(None, "--config", help="Path to skill-guard.yaml")
FORMAT_OPT = typer.Option("text", "--format", help="Output format: text|json|md|html")
REPO_ROOT_OPT = typer.Option(".", "--repo-root", help="Repository root for ownership checks")


def monitor_cmd(
    catalog_path: Path = CATALOG_OPT,
    endpoint: str | None = ENDPOINT_OPT,
    static_only: bool = STATIC_ONLY_OPT,
    config_path: Path | None = CONFIG_OPT,
    format: str = FORMAT_OPT,
    repo_root: Path = REPO_ROOT_OPT,
) -> None:
    """Monitor all non-deprecated catalog skills and produce a health report."""
    started = time.perf_counter()
    try:
        config = load_config(config_path)
    except ConfigError as e:
        typer.echo(f"Config error: {e}")
        raise typer.Exit(code=3) from e

    manager = CatalogManager()
    catalog = manager.load_catalog(catalog_path)
    repo_root = repo_root.resolve()
    resolved_endpoint = endpoint or config.test.endpoint

    statuses: list[SkillHealthStatus] = []
    deprecated_skipped = 0
    updated_entries = []
    now = datetime.now(UTC)

    for entry in catalog.skills:
        if entry.stage == "deprecated":
            deprecated_skipped += 1
            updated_entries.append(entry)
            continue

        findings: list[str] = []
        old_stage = entry.stage
        healthy_checks = True
        updated_entry = entry.model_copy(deep=True)

        skill_path = Path(entry.path)
        if not skill_path.is_absolute():
            skill_path = (repo_root / skill_path).resolve()

        try:
            skill = parse_skill(skill_path)
            validation = run_validation(skill, config.validate)
            security = run_security_scan(skill, config.secure)
            conflict = compute_similarity(skill, catalog_path, config.conflict)
            updated_entry.quality_score = validation.score

            if validation.blockers > 0:
                healthy_checks = False
                findings.append(f"validation blockers: {validation.blockers}")
            if not security.passed:
                healthy_checks = False
                findings.append(
                    "security failed "
                    f"(critical={security.critical_count}, high={security.high_count})"
                )
            if not conflict.passed:
                healthy_checks = False
                findings.append(
                    "conflict check failed "
                    f"(high={conflict.high_conflicts}, medium={conflict.medium_conflicts})"
                )

            if not static_only and resolved_endpoint:
                test_cfg = TestConfig.model_validate(
                    {
                        **config.test.model_dump(),
                        "endpoint": resolved_endpoint,
                    }
                )
                test_result = asyncio.run(run_agent_tests(skill, test_cfg))
                if not test_result.passed:
                    healthy_checks = False
                    findings.append(
                        f"agent tests failed ({test_result.failed_tests}/{test_result.total_tests})"
                    )
            elif not static_only and not resolved_endpoint:
                findings.append("agent test skipped: endpoint not configured")

        except SkillParseError as e:
            healthy_checks = False
            findings.append(f"parse error: {e}")
        except Exception as e:
            healthy_checks = False
            findings.append(f"monitor error: {e}")

        updated_entry.last_eval_run = now
        if healthy_checks:
            updated_entry.last_eval_passed = now
            updated_entry.consecutive_eval_failures = 0
        else:
            updated_entry.consecutive_eval_failures += 1

        stale_warning = check_staleness(updated_entry, config.monitor.stale_threshold_days)
        if stale_warning:
            findings.append(stale_warning)
            healthy_checks = False

        if config.monitor.check_ownership:
            ownership_warning = check_ownership(
                updated_entry,
                repo_root,
                config.monitor.ownership_files,
                config.monitor.ownership_fallback,
            )
            if ownership_warning:
                findings.append(ownership_warning)
                healthy_checks = False

        transitioned_entry, transition_messages = apply_stage_transitions(
            updated_entry, config.monitor, repo_root
        )
        findings.extend(transition_messages)
        transitioned = transitioned_entry.stage != old_stage

        statuses.append(
            SkillHealthStatus(
                skill_name=transitioned_entry.name,
                stage=transitioned_entry.stage,
                healthy=healthy_checks and transitioned_entry.stage != "degraded",
                findings=findings,
                transitioned=transitioned,
                old_stage=old_stage if transitioned else None,
                new_stage=transitioned_entry.stage if transitioned else None,
            )
        )
        updated_entries.append(transitioned_entry)

    updated_catalog = Catalog(
        version=catalog.version,
        updated=datetime.now(UTC),
        skills=updated_entries,
    )
    _save_catalog_atomic(updated_catalog, catalog_path)

    degraded = sum(1 for s in statuses if s.stage == "degraded")
    failing = sum(1 for s in statuses if (not s.healthy and s.stage != "degraded"))
    healthy = sum(1 for s in statuses if s.healthy)
    report = MonitorReport(
        generated_at=datetime.now(UTC),
        total_skills=len(statuses),
        healthy=healthy,
        degraded=degraded,
        failing=failing,
        deprecated_skipped=deprecated_skipped,
        run_time_seconds=round(time.perf_counter() - started, 3),
        skills=statuses,
        endpoint=resolved_endpoint,
    )

    if config.monitor.notify.slack_webhook:
        try:
            send_slack_notification(config.monitor.notify.slack_webhook, report)
        except Exception as e:
            typer.echo(f"Slack notify error: {e}")

    if config.monitor.notify.github_issues and config.monitor.notify.github_token:
        for status in statuses:
            if status.healthy or status.stage == "degraded":
                continue
            try:
                create_github_issue(
                    token=config.monitor.notify.github_token,
                    repo=config.monitor.notify.github_repo or "",
                    skill_name=status.skill_name,
                    findings=status.findings,
                )
            except Exception as e:
                typer.echo(f"GitHub issue error for {status.skill_name}: {e}")

    _emit_report(report, format)

    if report.failing > 0 or report.degraded > 0:
        raise typer.Exit(code=1)


def _emit_report(report: MonitorReport, output_format: str) -> None:
    if output_format == "json":
        typer.echo(format_as_json(report, command="monitor"))
        return
    if output_format in ("md", "markdown"):
        typer.echo(_format_markdown(report))
        return
    if output_format == "html":
        typer.echo(format_as_html(report))
        return
    typer.echo(_format_text(report))


def _format_text(report: MonitorReport) -> str:
    lines = [
        "skill-guard monitor",
        f"generated_at={report.generated_at.isoformat()} runtime={report.run_time_seconds:.2f}s",
        (
            f"total={report.total_skills} healthy={report.healthy} degraded={report.degraded} "
            f"failing={report.failing} deprecated_skipped={report.deprecated_skipped}"
        ),
    ]
    for status in report.skills:
        lines.append(
            f"- {status.skill_name}: stage={status.stage} healthy={status.healthy} "
            f"findings={len(status.findings)}"
        )
        for finding in status.findings:
            lines.append(f"  * {finding}")
    return "\n".join(lines)


def _format_markdown(report: MonitorReport) -> str:
    rows = []
    for status in report.skills:
        findings = "<br>".join(status.findings) if status.findings else "-"
        rows.append(
            f"| {status.skill_name} | {status.stage} | "
            f"{'yes' if status.healthy else 'no'} | {findings} |"
        )
    if not rows:
        rows.append("| - | - | - | - |")

    return (
        "## skill-guard monitor\n\n"
        f"- generated_at: {report.generated_at.isoformat()}\n"
        f"- runtime_seconds: {report.run_time_seconds:.2f}\n"
        f"- total_skills: {report.total_skills}\n"
        f"- healthy: {report.healthy}\n"
        f"- degraded: {report.degraded}\n"
        f"- failing: {report.failing}\n"
        f"- deprecated_skipped: {report.deprecated_skipped}\n\n"
        "| Skill | Stage | Healthy | Findings |\n|---|---|---|---|\n" + "\n".join(rows)
    )


def _save_catalog_atomic(catalog: Catalog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)

    with tmp_path.open("w", encoding="utf-8") as f:
        yaml.dump(catalog.model_dump(mode="json"), f)

    os.rename(tmp_path, path)
