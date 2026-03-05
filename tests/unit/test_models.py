from datetime import datetime
from pathlib import Path

from skill_guard.models import (
    Catalog,
    CatalogEntry,
    CheckResult,
    ConflictMatch,
    ConflictResult,
    EvalConfig,
    EvalExpectation,
    EvalTest,
    ParsedSkill,
    SecurityFinding,
    SecurityResult,
    SkillMetadata,
    ValidationResult,
)


def test_models_round_trip():
    meta = SkillMetadata(name="test-skill", description="Use when testing.")
    eval_cfg = EvalConfig(tests=[EvalTest(name="t1", prompt_file="a.md", expect=EvalExpectation())])
    skill = ParsedSkill(
        path=Path("/tmp/skill"),
        skill_md_path=Path("/tmp/skill/SKILL.md"),
        metadata=meta,
        body="body",
        body_line_count=1,
        has_scripts=False,
        scripts=[],
        has_references=False,
        references=[],
        has_assets=False,
        has_evals=True,
        evals_config=eval_cfg,
    )

    val = ValidationResult(
        skill_name="test-skill",
        skill_path=Path("/tmp/skill"),
        checks=[CheckResult(check_name="x", passed=True, severity="info", message="ok")],
        score=100,
        grade="A",
        passed=True,
        warnings=0,
        blockers=0,
    )

    sec = SecurityResult(
        skill_name="test-skill",
        findings=[
            SecurityFinding(
                id="CRED-001",
                severity="critical",
                category="CREDENTIALS",
                file="SKILL.md",
                line=1,
                pattern="x",
                matched_text="abcd****",
                description="x",
                suggestion="y",
                suppressed=False,
            )
        ],
        passed=False,
        critical_count=1,
        high_count=0,
        medium_count=0,
        low_count=0,
    )

    conflict = ConflictResult(
        skill_name="test-skill",
        matches=[
            ConflictMatch(
                existing_skill_name="other",
                similarity_score=0.8,
                severity="high",
                overlapping_phrases=["test"],
                suggestions=["merge"],
            )
        ],
        name_collision=False,
        passed=False,
        high_conflicts=1,
        medium_conflicts=0,
    )

    catalog = Catalog(
        updated=datetime.utcnow(),
        skills=[
            CatalogEntry(
                name="test-skill",
                description="desc",
                author="me",
                version="1.0",
                stage="staging",
                registered=datetime.utcnow(),
                last_updated=datetime.utcnow(),
                quality_score=90,
                path="./skills/test",
            )
        ],
    )

    # Round trip
    assert ParsedSkill.model_validate(skill.model_dump()).metadata.name == "test-skill"
    assert ValidationResult.model_validate(val.model_dump()).score == 100
    assert SecurityResult.model_validate(sec.model_dump()).critical_count == 1
    assert ConflictResult.model_validate(conflict.model_dump()).high_conflicts == 1
    assert Catalog.model_validate(catalog.model_dump()).skills[0].name == "test-skill"
