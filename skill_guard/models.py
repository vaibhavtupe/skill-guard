"""
Pydantic v2 data models for skill-guard.
All core types used across the CLI and engine modules.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Skill parsing models
# ---------------------------------------------------------------------------


class SkillMetadata(BaseModel):
    """Parsed SKILL.md frontmatter fields."""

    name: str
    description: str
    license: str | None = None
    compatibility: list[str] | None = None
    metadata: dict[str, Any] | None = None
    allowed_tools: list[str] | None = None
    conflict_ignore: list[str] = Field(default_factory=list)

    # Derived from metadata dict
    @property
    def author(self) -> str | None:
        if self.metadata:
            return self.metadata.get("author")
        return None

    @property
    def version(self) -> str | None:
        if self.metadata:
            return self.metadata.get("version")
        return None

    @property
    def tags(self) -> list[str]:
        if self.metadata:
            return self.metadata.get("tags", [])
        return []


class EvalExpectation(BaseModel):
    """Expected outcomes for a single eval test case."""

    contains: list[str] = Field(default_factory=list)
    not_contains: list[str] = Field(default_factory=list)
    max_latency_ms: int | None = None
    min_length: int | None = None
    skill_triggered: str | None = None
    skill_not_triggered: str | None = None


class EvalTest(BaseModel):
    """A single eval test case."""

    name: str
    prompt_file: str | None = None
    prompt: str | None = None
    expect: EvalExpectation
    expected_output: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _ensure_prompt_source(self) -> EvalTest:
        if not self.prompt_file and not self.prompt:
            raise ValueError("Eval test must define either prompt_file or prompt")
        return self


class EvalConfig(BaseModel):
    """Full evals/config.yaml structure."""

    tests: list[EvalTest]


class ParsedSkill(BaseModel):
    """Fully parsed skill directory."""

    path: Path
    skill_md_path: Path
    metadata: SkillMetadata
    body: str
    body_line_count: int
    has_scripts: bool
    scripts: list[Path] = Field(default_factory=list)
    has_references: bool
    references: list[Path] = Field(default_factory=list)
    has_assets: bool
    has_evals: bool
    evals_config: EvalConfig | None = None

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Validation result models
# ---------------------------------------------------------------------------

SeverityLevel = Literal["blocker", "warning", "info"]
Grade = Literal["A", "B", "C", "D", "F"]


class RuleSet(str, Enum):  # noqa: UP042
    DEFAULT = "default"
    ANTHROPIC_SPEC = "anthropic_spec"


class Finding(BaseModel):
    """Generic rule finding used by internal validators."""

    rule_id: str
    severity: SeverityLevel
    message: str
    suggestion: str | None = None
    rule_set: RuleSet = RuleSet.DEFAULT


class CheckResult(BaseModel):
    """Result of a single validation check."""

    check_name: str
    passed: bool
    severity: SeverityLevel
    message: str
    suggestion: str | None = None


class ValidationResult(BaseModel):
    """Aggregate output of skill-guard validate."""

    skill_name: str
    skill_path: Path
    checks: list[CheckResult]
    score: int = Field(ge=0, le=100)
    grade: Grade
    passed: bool
    warnings: int
    blockers: int

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Security result models
# ---------------------------------------------------------------------------

SecuritySeverity = Literal["critical", "high", "medium", "low"]
SecurityCategory = Literal[
    "CREDENTIALS",
    "INJECTION",
    "DANGEROUS_EXEC",
    "DATA_EXFILTRATION",
    "PROMPT_INJECTION",
    "SCOPE",
]


class SecurityFinding(BaseModel):
    """A single security finding."""

    id: str
    severity: SecuritySeverity
    category: SecurityCategory
    file: str
    line: int | None = None
    pattern: str
    matched_text: str
    description: str
    suggestion: str
    suppressed: bool = False


class SecurityResult(BaseModel):
    """Aggregate output of skill-guard secure."""

    skill_name: str
    findings: list[SecurityFinding]
    passed: bool
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int


# ---------------------------------------------------------------------------
# Conflict detection models
# ---------------------------------------------------------------------------

ConflictSeverity = Literal["high", "medium", "low"]


class ConflictMatch(BaseModel):
    """A single skill conflict match."""

    existing_skill_name: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    severity: ConflictSeverity
    overlapping_phrases: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ConflictResult(BaseModel):
    """Aggregate output of skill-guard conflict."""

    skill_name: str
    matches: list[ConflictMatch]
    name_collision: bool
    name_collision_with: str | None = None
    passed: bool
    high_conflicts: int
    medium_conflicts: int


CheckStatus = Literal["passed", "warning", "failed", "skipped"]


class CheckSkillReport(BaseModel):
    """Per-skill report emitted by the repo-aware check command."""

    skill_name: str
    skill_path: Path
    target_status: Literal["modified", "renamed", "deleted", "single"]
    previous_skill_path: Path | None = None
    validation: str
    security: str
    conflict: str
    test: str
    status: CheckStatus
    summary: str
    result: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class CheckRunReport(BaseModel):
    """Aggregate report for a repo-aware `skill-guard check` run."""

    mode: Literal["single", "changed"]
    target_root: Path
    against: Path
    base_ref: str | None = None
    head_ref: str | None = None
    total_skills: int
    checked_skills: int
    skipped_skills: int
    passed: int
    warnings: int
    failed: int
    status: CheckStatus
    summary: str
    skills: list[CheckSkillReport]

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SkillGateError(Exception):
    """Base error for skill-guard."""


class SkillParseError(SkillGateError):
    """Raised when a skill directory cannot be parsed."""


class ConfigError(SkillGateError):
    """Raised when skill-guard.yaml is invalid or missing."""
