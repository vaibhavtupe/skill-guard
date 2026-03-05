"""
Pydantic v2 data models for skill-gate.
All core types used across the CLI and engine modules.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Skill parsing models
# ---------------------------------------------------------------------------


class SkillMetadata(BaseModel):
    """Parsed SKILL.md frontmatter fields."""

    name: str
    description: str
    license: Optional[str] = None
    compatibility: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None
    allowed_tools: Optional[list[str]] = None

    # Derived from metadata dict
    @property
    def author(self) -> Optional[str]:
        if self.metadata:
            return self.metadata.get("author")
        return None

    @property
    def version(self) -> Optional[str]:
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
    max_latency_ms: Optional[int] = None
    min_length: Optional[int] = None
    skill_triggered: Optional[str] = None
    skill_not_triggered: Optional[str] = None


class EvalTest(BaseModel):
    """A single eval test case."""

    name: str
    prompt_file: str
    expect: EvalExpectation
    description: Optional[str] = None


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
    evals_config: Optional[EvalConfig] = None

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Validation result models
# ---------------------------------------------------------------------------

SeverityLevel = Literal["blocker", "warning", "info"]
Grade = Literal["A", "B", "C", "D", "F"]


class CheckResult(BaseModel):
    """Result of a single validation check."""

    check_name: str
    passed: bool
    severity: SeverityLevel
    message: str
    suggestion: Optional[str] = None


class ValidationResult(BaseModel):
    """Aggregate output of skill-gate validate."""

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
    line: Optional[int] = None
    pattern: str
    matched_text: str
    description: str
    suggestion: str
    suppressed: bool = False


class SecurityResult(BaseModel):
    """Aggregate output of skill-gate secure."""

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
    """Aggregate output of skill-gate conflict."""

    skill_name: str
    matches: list[ConflictMatch]
    name_collision: bool
    name_collision_with: Optional[str] = None
    passed: bool
    high_conflicts: int
    medium_conflicts: int


# ---------------------------------------------------------------------------
# Agent test result models (Phase 2 — stubs in Phase 1)
# ---------------------------------------------------------------------------


class EvalTestResult(BaseModel):
    """Result of a single eval test execution against a real agent."""

    test_name: str
    passed: bool
    prompt: str
    response_text: str
    latency_ms: int
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    skill_triggered: Optional[str] = None
    tool_calls: list[str] = Field(default_factory=list)


class AgentTestResult(BaseModel):
    """Aggregate output of skill-gate test."""

    skill_name: str
    endpoint: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    pass_rate: float
    results: list[EvalTestResult]
    total_time_seconds: float
    avg_latency_ms: float
    passed: bool


# ---------------------------------------------------------------------------
# Unified pipeline result
# ---------------------------------------------------------------------------


class CheckPipelineResult(BaseModel):
    """Result of the unified skill-gate check command."""

    skill_name: str
    validation: ValidationResult
    security: SecurityResult
    conflict: ConflictResult
    agent_test: Optional[AgentTestResult] = None
    passed: bool
    summary: str


# ---------------------------------------------------------------------------
# Catalog models
# ---------------------------------------------------------------------------

SkillStage = Literal["staging", "production", "degraded", "deprecated"]


class CatalogEntry(BaseModel):
    """A single skill entry in the catalog."""

    name: str
    description: str
    author: str
    version: str
    stage: SkillStage
    registered: datetime
    last_updated: datetime
    last_eval_passed: Optional[datetime] = None
    last_eval_run: Optional[datetime] = None
    quality_score: int = Field(ge=0, le=100)
    path: str
    tags: list[str] = Field(default_factory=list)
    eval_count: int = 0
    consecutive_eval_failures: int = 0


class Catalog(BaseModel):
    """Full skill catalog."""

    version: str = "1.0"
    updated: datetime
    skills: list[CatalogEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SkillGateError(Exception):
    """Base error for skill-gate."""


class SkillParseError(SkillGateError):
    """Raised when a skill directory cannot be parsed."""


class ConfigError(SkillGateError):
    """Raised when skill-gate.yaml is invalid or missing."""


class HookError(SkillGateError):
    """Raised when a pre/post test hook fails."""
