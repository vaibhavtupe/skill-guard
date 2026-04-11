"""CLI command: skill-guard check."""

from __future__ import annotations

import asyncio
import subprocess
import warnings
from pathlib import Path
from typing import Any

import typer

from skill_guard.config import ConfigError, SkillGateConfig, load_config
from skill_guard.engine.agent_runner import run_agent_tests
from skill_guard.engine.quality import run_validation
from skill_guard.engine.repo_targets import resolve_changed_skill_selection
from skill_guard.engine.security import run_security_scan
from skill_guard.engine.similarity import compute_similarity
from skill_guard.models import (
    CheckRunReport,
    CheckSkillReport,
    HealthCheckTimeoutError,
    HookError,
    SkillParseError,
)
from skill_guard.output.json_out import format_as_json
from skill_guard.output.markdown import format_as_markdown
from skill_guard.parser import parse_skill

TARGET_PATH_ARG = typer.Argument(
    ...,
    help="Path to a skill directory, or a skills root when used with --changed",
)
AGAINST_OPT = typer.Option(
    None,
    "--against",
    help="Skills dir or catalog YAML. Defaults to the target parent, or the target root for --changed",
)
ENDPOINT_OPT = typer.Option(None, "--endpoint", help="Agent endpoint URL")
CONFIG_OPT = typer.Option(None, "--config", help="Path to skill-guard.yaml")
FORMAT_OPT = typer.Option(None, "--format", help="Output format: text|json|md")
CHANGED_OPT = typer.Option(False, "--changed", help="Check all changed skills under TARGET_PATH")
BASE_REF_OPT = typer.Option(None, "--base-ref", help="Base git ref used with --changed")
HEAD_REF_OPT = typer.Option(None, "--head-ref", help="Head git ref used with --changed")


def _emit_single(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        typer.echo(format_as_json(payload, command="check"))
        return
    if output_format in ("md", "markdown"):
        typer.echo(
            "## skill-guard check\n\n"
            f"- skill: {payload['skill_name']}\n"
            f"- validation: {payload['validation']}\n"
            f"- security: {payload['security']}\n"
            f"- conflict: {payload['conflict']}\n"
            f"- test: {payload['test']}\n"
            f"- status: {payload['status']}\n"
            f"- summary: {payload['summary']}\n"
        )
        return

    typer.echo(
        f"skill={payload['skill_name']} validation={payload['validation']} "
        f"security={payload['security']} conflict={payload['conflict']} "
        f"test={payload['test']} status={payload['status']}\n{payload['summary']}"
    )


def _emit_run(report: CheckRunReport, output_format: str) -> None:
    if output_format == "json":
        typer.echo(format_as_json(report, command="check"))
        return
    if output_format in ("md", "markdown"):
        typer.echo(format_as_markdown(report, command="check"))
        return
    typer.echo(_format_text(report))


def _format_text(report: CheckRunReport) -> str:
    lines = [
        f"mode={report.mode} status={report.status} total={report.total_skills} "
        f"checked={report.checked_skills} skipped={report.skipped_skills}",
        report.summary,
    ]
    for skill in report.skills:
        lines.append(
            f"- {skill.skill_name} [{skill.target_status}] "
            f"validation={skill.validation} security={skill.security} "
            f"conflict={skill.conflict} test={skill.test} status={skill.status}"
        )
    return "\n".join(lines)


def _single_payload(report: CheckSkillReport) -> dict[str, Any]:
    return {
        "skill_name": report.skill_name,
        "validation": report.validation,
        "security": report.security,
        "conflict": report.conflict,
        "test": report.test,
        "status": report.status,
        "summary": report.summary,
        "result": report.result,
    }


def _normalize_validation_for_target(
    validation,
    *,
    skill_name: str,
    target_status: str,
    previous_skill_path: Path | None,
):
    if target_status != "renamed" or previous_skill_path is None:
        return validation
    if previous_skill_path.name != skill_name:
        return validation

    updated_checks = []
    changed = False
    for check in validation.checks:
        if check.check_name == "directory_name_matches" and not check.passed:
            updated_checks.append(
                check.model_copy(
                    update={
                        "passed": True,
                        "message": (
                            "Directory rename accepted for changed-skill evaluation; "
                            f"previous directory '{previous_skill_path.name}' matched skill name"
                        ),
                        "suggestion": None,
                    }
                )
            )
            changed = True
            continue
        updated_checks.append(check)

    if not changed:
        return validation

    blockers = sum(
        1 for check in updated_checks if not check.passed and check.severity == "blocker"
    )
    warnings_count = sum(
        1 for check in updated_checks if not check.passed and check.severity == "warning"
    )
    return validation.model_copy(
        update={
            "checks": updated_checks,
            "passed": blockers == 0,
            "blockers": blockers,
            "warnings": warnings_count,
        }
    )


def _run_skill_check(
    skill_path: Path,
    *,
    against_source: Path,
    endpoint: str | None,
    config: SkillGateConfig,
    target_status: str,
    previous_skill_path: Path | None = None,
) -> tuple[CheckSkillReport, int]:
    try:
        skill = parse_skill(skill_path)
    except SkillParseError as exc:
        return (
            CheckSkillReport(
                skill_name=skill_path.name,
                skill_path=skill_path,
                target_status=target_status,  # type: ignore[arg-type]
                previous_skill_path=previous_skill_path,
                validation="failed",
                security="skipped",
                conflict="skipped",
                test="skipped",
                status="failed",
                summary=f"Parse error: {exc}",
                result={},
            ),
            4,
        )

    validation = run_validation(skill, config.validate)
    validation = _normalize_validation_for_target(
        validation,
        skill_name=skill.metadata.name,
        target_status=target_status,
        previous_skill_path=previous_skill_path,
    )
    validation_status = "passed" if validation.warnings == 0 else "warning"
    if validation.blockers > 0:
        return (
            CheckSkillReport(
                skill_name=skill.metadata.name,
                skill_path=skill.path,
                target_status=target_status,  # type: ignore[arg-type]
                previous_skill_path=previous_skill_path,
                validation="failed",
                security="skipped",
                conflict="skipped",
                test="skipped",
                status="failed",
                summary=f"Validation failed with {validation.blockers} blocker(s).",
                result={"validation": validation.model_dump(mode="json")},
            ),
            1,
        )

    security = run_security_scan(skill, config.secure)
    if not security.passed:
        return (
            CheckSkillReport(
                skill_name=skill.metadata.name,
                skill_path=skill.path,
                target_status=target_status,  # type: ignore[arg-type]
                previous_skill_path=previous_skill_path,
                validation=validation_status,
                security="failed",
                conflict="skipped",
                test="skipped",
                status="failed",
                summary="Security scan failed.",
                result={
                    "validation": validation.model_dump(mode="json"),
                    "security": security.model_dump(mode="json"),
                },
            ),
            1,
        )

    try:
        conflict = compute_similarity(skill, against_source, config.conflict)
    except ConfigError as exc:
        return (
            CheckSkillReport(
                skill_name=skill.metadata.name,
                skill_path=skill.path,
                target_status=target_status,  # type: ignore[arg-type]
                previous_skill_path=previous_skill_path,
                validation=validation_status,
                security="passed",
                conflict="failed",
                test="skipped",
                status="failed",
                summary=f"Config error: {exc}",
                result={},
            ),
            3,
        )

    if not conflict.passed:
        return (
            CheckSkillReport(
                skill_name=skill.metadata.name,
                skill_path=skill.path,
                target_status=target_status,  # type: ignore[arg-type]
                previous_skill_path=previous_skill_path,
                validation=validation_status,
                security="passed",
                conflict="failed",
                test="skipped",
                status="failed",
                summary="Conflict detection found blocking overlap.",
                result={
                    "validation": validation.model_dump(mode="json"),
                    "security": security.model_dump(mode="json"),
                    "conflict": conflict.model_dump(mode="json"),
                },
            ),
            1,
        )

    test_status = "skipped"
    test_result = None
    if endpoint:
        config.test.endpoint = endpoint
        try:
            test_result = asyncio.run(run_agent_tests(skill, config.test))
        except HealthCheckTimeoutError as exc:
            return (
                CheckSkillReport(
                    skill_name=skill.metadata.name,
                    skill_path=skill.path,
                    target_status=target_status,  # type: ignore[arg-type]
                    previous_skill_path=previous_skill_path,
                    validation=validation_status,
                    security="passed",
                    conflict="passed",
                    test="failed",
                    status="failed",
                    summary=f"Test setup error: {exc}",
                    result={},
                ),
                6,
            )
        except HookError as exc:
            return (
                CheckSkillReport(
                    skill_name=skill.metadata.name,
                    skill_path=skill.path,
                    target_status=target_status,  # type: ignore[arg-type]
                    previous_skill_path=previous_skill_path,
                    validation=validation_status,
                    security="passed",
                    conflict="passed",
                    test="failed",
                    status="failed",
                    summary=f"Test setup error: {exc}",
                    result={},
                ),
                5,
            )

        if test_result.passed:
            test_status = "passed"
        elif test_result.failed_tests > 0:
            return (
                CheckSkillReport(
                    skill_name=skill.metadata.name,
                    skill_path=skill.path,
                    target_status=target_status,  # type: ignore[arg-type]
                    previous_skill_path=previous_skill_path,
                    validation=validation_status,
                    security="passed",
                    conflict="passed",
                    test="failed",
                    status="failed",
                    summary="Agent evals failed with blocking failures.",
                    result={
                        "validation": validation.model_dump(mode="json"),
                        "security": security.model_dump(mode="json"),
                        "conflict": conflict.model_dump(mode="json"),
                        "test": test_result.model_dump(mode="json"),
                    },
                ),
                1,
            )
        else:
            test_status = "warning"

    has_warning = validation_status == "warning" or test_status == "warning"
    fail_on_warning = config.ci.fail_on_warning and has_warning
    final_status = "failed" if fail_on_warning else ("warning" if has_warning else "passed")

    return (
        CheckSkillReport(
            skill_name=skill.metadata.name,
            skill_path=skill.path,
            target_status=target_status,  # type: ignore[arg-type]
            previous_skill_path=previous_skill_path,
            validation=validation_status,
            security="passed",
            conflict="passed",
            test=test_status,
            status=final_status,  # type: ignore[arg-type]
            summary=(
                "All blocking checks passed."
                if not has_warning
                else (
                    "Warnings are configured to fail this CI check."
                    if fail_on_warning
                    else "Blocking checks passed with warnings."
                )
            ),
            result={
                "validation": validation.model_dump(mode="json"),
                "security": security.model_dump(mode="json"),
                "conflict": conflict.model_dump(mode="json"),
                **(
                    {"test": test_result.model_dump(mode="json")} if test_result is not None else {}
                ),
            },
        ),
        1 if fail_on_warning else (2 if has_warning else 0),
    )


def _build_run_report(
    *,
    mode: str,
    target_root: Path,
    against_source: Path,
    skills: list[CheckSkillReport],
    base_ref: str | None = None,
    head_ref: str | None = None,
) -> CheckRunReport:
    passed = sum(1 for skill in skills if skill.status == "passed")
    warnings_count = sum(1 for skill in skills if skill.status == "warning")
    failed = sum(1 for skill in skills if skill.status == "failed")
    skipped = sum(1 for skill in skills if skill.status == "skipped")
    checked = len(skills) - skipped

    if failed > 0:
        final_status = "failed"
    elif warnings_count > 0:
        final_status = "warning"
    else:
        final_status = "passed"

    if not skills:
        summary = "No changed skills detected."
    elif checked == 0:
        summary = f"No checkable changed skills. {skipped} skill(s) skipped."
    else:
        summary = (
            f"{checked} skill(s) checked: {passed} passed, "
            f"{warnings_count} warning, {failed} failed, {skipped} skipped."
        )

    return CheckRunReport(
        mode=mode,  # type: ignore[arg-type]
        target_root=target_root,
        against=against_source,
        base_ref=base_ref,
        head_ref=head_ref,
        total_skills=len(skills),
        checked_skills=checked,
        skipped_skills=skipped,
        passed=passed,
        warnings=warnings_count,
        failed=failed,
        status=final_status,  # type: ignore[arg-type]
        summary=summary,
        skills=skills,
    )


def check_cmd(
    target_path: Path = TARGET_PATH_ARG,
    against: Path | None = AGAINST_OPT,
    endpoint: str | None = ENDPOINT_OPT,
    config_path: Path | None = CONFIG_OPT,
    output_format: str | None = FORMAT_OPT,
    changed: bool = CHANGED_OPT,
    base_ref: str | None = BASE_REF_OPT,
    head_ref: str | None = HEAD_REF_OPT,
) -> None:
    """Run validate + secure + conflict + test pipeline for one or more skills."""
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}")
        raise typer.Exit(code=3) from exc

    resolved_output_format = output_format or config.ci.output_format
    if config.ci.post_pr_comment:
        warnings.warn(
            "ci.post_pr_comment is not yet implemented and has no effect.",
            stacklevel=2,
        )

    resolved_endpoint = endpoint or config.test.endpoint

    if changed:
        try:
            selection = resolve_changed_skill_selection(
                target_path,
                base_ref=base_ref,
                head_ref=head_ref,
            )
        except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            typer.echo(f"Changed-skill detection error: {exc}")
            raise typer.Exit(code=3) from exc

        against_source = (against or selection.target_root).resolve()
        reports: list[CheckSkillReport] = []
        exit_code = 0

        for target in selection.targets:
            report, skill_exit = _run_skill_check(
                target.root,
                against_source=against_source,
                endpoint=resolved_endpoint,
                config=config,
                target_status=target.status,
                previous_skill_path=target.previous_root,
            )
            reports.append(report)
            exit_code = max(exit_code, skill_exit)

        for deleted_root in selection.deleted_roots:
            reports.append(
                CheckSkillReport(
                    skill_name=deleted_root.name,
                    skill_path=deleted_root,
                    target_status="deleted",
                    validation="skipped",
                    security="skipped",
                    conflict="skipped",
                    test="skipped",
                    status="skipped",
                    summary="Skill was deleted in the compared diff.",
                    result={},
                )
            )

        run_report = _build_run_report(
            mode="changed",
            target_root=selection.target_root,
            against_source=against_source,
            skills=reports,
            base_ref=selection.base_ref,
            head_ref=selection.head_ref,
        )
        _emit_run(run_report, resolved_output_format)

        if exit_code in (3, 4, 5, 6):
            raise typer.Exit(code=exit_code)
        if run_report.failed > 0:
            raise typer.Exit(code=1)
        return

    against_source = (against or target_path.parent).resolve()
    single_report, exit_code = _run_skill_check(
        target_path,
        against_source=against_source,
        endpoint=resolved_endpoint,
        config=config,
        target_status="single",
    )
    _emit_single(_single_payload(single_report), resolved_output_format)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)
