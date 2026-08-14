"""Fail-closed preparation and formal runner for T02 Wave C regression.

The legacy schema-only boundary remains available for compatibility.  The
formal runner independently verifies the Captain confirmation and canonical
source, reproduces the frozen selection, and either performs four unique real
runs or emits secret-free ``CASE_BLOCKED`` evidence.  It has no mock fallback.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.contracts.revision import IssueClosure, ReviewFeedback
from app.workflow.explainable_revision import (
    ExperimentRevisionContext,
    StructuredRevisionDiff,
)
from app.workflow.revision_consumer import LineageView


AUTHORITY_SOURCE = "docs/governance/task-requirements/T02.yaml"
AUTHORITY_COMMIT = "1642ea05e88b853f18d24739d9d2134c3448eb7b"
Q028_QUESTION = "Will it be possible to cure all cancers?"
Q028_CANONICAL_INPUT_HASH = (
    "badcae2fec281a0bbaec81b36d8ed4a149696db855d0f399e7cbe382fdc78da8"
)
FLAGSHIP_SOURCE = "experiments/flagship/selection_manifest.json"
REQUIRED_LABELS = ("Q028", "flagship", "random_1", "random_2", "random_3")

CAPTAIN_AUTHORITY_URL = (
    "https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/"
    "pull/37#issuecomment-5291084709"
)
CAPTAIN_ORIGINAL_AUTHORITY_URL = (
    "https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/"
    "pull/37#issuecomment-5289677150"
)
CAPTAIN_LOGIN = "liuyanbo12"
CAPTAIN_COMMENT_ID = 5291084709
FORMAL_RANDOM_CASE_IDS = ("Q095", "Q045", "Q100")
FORMAL_RANDOM_SEED = 20260814
FORMAL_LOGICAL_LABELS = (
    "Q028_REGRESSION",
    "FLAGSHIP",
    "RANDOM_Q095",
    "RANDOM_Q045",
    "RANDOM_Q100",
)
FORMAL_CASE_SPECS = (
    ("Q028_FLAGSHIP_SHARED", "Q028", ("Q028_REGRESSION", "FLAGSHIP"), True),
    ("RANDOM_Q095", "Q095", ("RANDOM_Q095",), False),
    ("RANDOM_Q045", "Q045", ("RANDOM_Q045",), False),
    ("RANDOM_Q100", "Q100", ("RANDOM_Q100",), False),
)
SOURCE_DOCUMENT_SHA256 = (
    "4bda50e8e3c90f8968f1bfd72ded4d9587ae80cd40ba66656a12c93abcf8e576"
)
SOURCE_DOCUMENT_URL = (
    "https://www.science.org/cms/asset/"
    "b09620dc-2937-45bd-9c29-3ea07c1f4a04/sjtu-booklet.pdf"
)
SELECTION_ALGORITHM = "random.Random(seed).sample(population,3)"

RequirementLabel = Literal["Q028", "flagship", "random_1", "random_2", "random_3"]
PromptHash = str


def canonical_sha256(value: Any) -> str:
    """Hash canonical UTF-8 JSON without applying Git or EOL filters."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return value


def _not_placeholder(value: str, field_name: str) -> str:
    normalized = value.strip()
    lowered = normalized.lower()
    if not normalized or any(token in lowered for token in ("todo", "tbd", "pending")):
        raise ValueError(f"{field_name} must contain a real authorized value")
    return normalized


class _ReleaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CaptainCaseAuthorization(_ReleaseModel):
    """The decisions that must come from a Captain review/comment."""

    schema_version: Literal[1] = 1
    status: Literal["captain_approved"]
    reviewer_login: str = Field(min_length=1)
    reference_url: str = Field(
        pattern=(
            r"^https://github\.com/sage125-ai-scientist-team/"
            r"SAGE125-AI-Scientist/pull/37#"
            r"(?:issuecomment|pullrequestreview)-[0-9]+$"
        )
    )
    authorized_at: datetime
    random_case_ids: tuple[str, str, str]
    random_seed: int | None = None
    selection_policy: str = Field(min_length=1)
    q028_flagship_execution: Literal["independent_runs", "shared_run"]
    metric004_semantic: Literal["random_case_count"]

    @model_validator(mode="after")
    def _validate_authorization(self) -> "CaptainCaseAuthorization":
        _aware(self.authorized_at, "authorized_at")
        _not_placeholder(self.reviewer_login, "reviewer_login")
        _not_placeholder(self.selection_policy, "selection_policy")
        if len(set(self.random_case_ids)) != 3:
            raise ValueError("Captain authorization must name three distinct random cases")
        if any(not value.startswith("Q") or len(value) != 4 for value in self.random_case_ids):
            raise ValueError("random case IDs must use the Qxxx canonical identity")
        return self


class ReleaseCaseSelection(_ReleaseModel):
    """One authorized case identity; this is selection data, not a run result."""

    schema_version: Literal[1] = 1
    requirement_label: RequirementLabel
    question_id: str = Field(pattern=r"^Q[0-9]{3}$")
    canonical_input: dict[str, Any]
    canonical_question: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_hash_algorithm: Literal["t07_canonical_question_record_sha256"] = (
        "t07_canonical_question_record_sha256"
    )
    source_reference: str = Field(min_length=1)
    shared_run_key: str | None = None

    @model_validator(mode="after")
    def _validate_identity(self) -> "ReleaseCaseSelection":
        source_id = self.canonical_input.get("id")
        if source_id is not None and source_id != self.question_id:
            raise ValueError("canonical input ID does not match question_id")
        source_question = self.canonical_input.get("question")
        if source_question is not None and source_question != self.canonical_question:
            raise ValueError("canonical input question does not match canonical_question")
        if self.requirement_label == "Q028":
            if (
                self.question_id != "Q028"
                or self.canonical_question != Q028_QUESTION
                or self.input_hash != Q028_CANONICAL_INPUT_HASH
            ):
                raise ValueError("Q028 selection does not match the frozen canonical input")
        if self.requirement_label == "flagship":
            if self.question_id != "Q028" or self.source_reference != FLAGSHIP_SOURCE:
                raise ValueError("flagship selection must use the frozen Q028 manifest")
        return self


class ReleaseSelectionManifest(_ReleaseModel):
    """The only manifest accepted by the formal harness."""

    schema_version: Literal[1] = 1
    authority_source: Literal[AUTHORITY_SOURCE] = AUTHORITY_SOURCE
    authority_commit: Literal[AUTHORITY_COMMIT] = AUTHORITY_COMMIT
    metric_id: Literal["T02-METRIC-004"] = "T02-METRIC-004"
    authorized_raw_threshold: Literal["3 个"] = "3 个"
    authorized_value: Literal[3] = 3
    authorized_semantic: Literal["random_case_count"] = "random_case_count"
    authorization: CaptainCaseAuthorization
    selected_at: datetime
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    cases: tuple[ReleaseCaseSelection, ...] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def _validate_case_set(self) -> "ReleaseSelectionManifest":
        _aware(self.selected_at, "selected_at")
        labels = tuple(case.requirement_label for case in self.cases)
        if labels != REQUIRED_LABELS:
            raise ValueError(f"release cases must be ordered as {REQUIRED_LABELS!r}")
        random_ids = tuple(case.question_id for case in self.cases[2:])
        if random_ids != self.authorization.random_case_ids:
            raise ValueError("random cases do not match Captain authorization")

        q028_case, flagship_case = self.cases[:2]
        if self.authorization.q028_flagship_execution == "shared_run":
            if not q028_case.shared_run_key or (
                q028_case.shared_run_key != flagship_case.shared_run_key
            ):
                raise ValueError("shared Q028/flagship execution requires one shared_run_key")
        elif q028_case.shared_run_key is not None or flagship_case.shared_run_key is not None:
            raise ValueError("independent Q028/flagship executions cannot share a run key")
        return self


class DatasetCaseRecord(_ReleaseModel):
    schema_version: Literal[1] = 1
    requirement_label: RequirementLabel
    question_id: str = Field(pattern=r"^Q[0-9]{3}$")
    canonical_input: dict[str, Any]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_reference: str = Field(min_length=1)


class ReleaseDatasetManifest(_ReleaseModel):
    """Canonical source snapshot binding for the authorized case set."""

    schema_version: Literal[1] = 1
    selection_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_catalog_path: str = Field(min_length=1)
    source_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_record_count: int = Field(ge=1)
    generated_at: datetime
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    cases: tuple[DatasetCaseRecord, ...] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def _validate_dataset(self) -> "ReleaseDatasetManifest":
        _aware(self.generated_at, "generated_at")
        if tuple(item.requirement_label for item in self.cases) != REQUIRED_LABELS:
            raise ValueError("dataset manifest must preserve the authorized case order")
        q028 = self.cases[0]
        if q028.question_id != "Q028" or q028.input_hash != Q028_CANONICAL_INPUT_HASH:
            raise ValueError("dataset manifest does not preserve canonical Q028")
        return self


class ReleaseCaseResult(_ReleaseModel):
    """Actual T02 full-chain evidence for exactly one requirement label."""

    schema_version: Literal[1] = 1
    requirement_label: RequirementLabel
    question_id: str = Field(pattern=r"^Q[0-9]{3}$")
    canonical_input: dict[str, Any]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    job_id: str | None = None
    started_at: datetime
    ended_at: datetime
    model: str = Field(min_length=1)
    mode: Literal["real"] = "real"
    mock_mode: Literal[False] = False
    truth_status: Literal["actual"] = "actual"
    v1_version_id: str = Field(min_length=1)
    v2_version_id: str = Field(min_length=1)
    v1_prompt_hash: PromptHash = Field(pattern=r"^[0-9a-f]{12,64}$")
    v2_prompt_hash: PromptHash = Field(pattern=r"^[0-9a-f]{12,64}$")
    reviewer_feedback: ReviewFeedback
    required_revisions: tuple[str, ...]
    revision_context: ExperimentRevisionContext
    feedback_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision_context_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    structured_diff: StructuredRevisionDiff
    diff_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    issue_closures: tuple[IssueClosure, ...]
    score_before: dict[str, float] = Field(min_length=1)
    score_after: dict[str, float] = Field(min_length=1)
    score_delta: dict[str, float] = Field(min_length=1)
    lineage: LineageView
    stop_reason: str | None = None
    unresolved_p0: int = Field(ge=0)
    unresolved_p1: int = Field(ge=0)
    validation_result: Literal["passed", "failed"]
    execution_status: Literal["succeeded", "failed", "timed_out"]
    evidence_provenance: tuple[str, ...] = Field(min_length=1)
    failure_reasons: tuple[str, ...] = ()
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    same_prompt_hash_false_iteration: bool
    passed: bool

    @model_validator(mode="after")
    def _validate_result(self) -> "ReleaseCaseResult":
        _aware(self.started_at, "started_at")
        _aware(self.ended_at, "ended_at")
        if self.ended_at < self.started_at:
            raise ValueError("ended_at cannot precede started_at")
        if (self.v1_version_id, self.v2_version_id) != (
            f"{self.run_id}:v1",
            f"{self.run_id}:v2",
        ):
            raise ValueError("release result requires direct canonical V1/V2 lineage")
        if self.lineage.run_id != self.run_id or self.lineage.version_ids != (
            self.v1_version_id,
            self.v2_version_id,
        ):
            raise ValueError("lineage does not match release result versions")
        if self.revision_context.parent_version_id != self.v1_version_id:
            raise ValueError("RevisionContext parent does not match V1")
        if self.revision_context.reviewer_feedback != self.reviewer_feedback:
            raise ValueError("RevisionContext feedback does not match Reviewer feedback")
        if tuple(self.reviewer_feedback.required_revisions) != self.required_revisions:
            raise ValueError("required revisions do not match Reviewer feedback")
        if self.feedback_fingerprint != canonical_sha256(
            self.reviewer_feedback.model_dump(mode="json")
        ):
            raise ValueError("feedback fingerprint does not match Reviewer feedback")
        if self.revision_context_fingerprint != canonical_sha256(
            self.revision_context.model_dump(mode="json")
        ):
            raise ValueError("revision context fingerprint does not match content")
        if self.diff_hash != self.structured_diff.fingerprint():
            raise ValueError("diff hash does not match canonical structured diff")

        fields = set(self.score_before) | set(self.score_after) | set(self.score_delta)
        if not fields or not (
            set(self.score_before) == set(self.score_after) == set(self.score_delta)
        ):
            raise ValueError("score before/after/delta fields must be identical")
        for name in fields:
            expected = self.score_after[name] - self.score_before[name]
            if not math.isclose(self.score_delta[name], expected, abs_tol=1e-12):
                raise ValueError(f"score delta is invalid for {name}")

        expected_p0 = sum(
            1
            for issue in self.issue_closures
            if issue.status == "open" and issue.category == "critical_issue"
        )
        expected_p1 = sum(
            1
            for issue in self.issue_closures
            if issue.status == "open" and issue.category == "required_revision"
        )
        if (self.unresolved_p0, self.unresolved_p1) != (expected_p0, expected_p1):
            raise ValueError("unresolved P0/P1 counts do not match IssueClosure records")

        same_hash = self.v1_prompt_hash == self.v2_prompt_hash
        if self.same_prompt_hash_false_iteration != same_hash:
            raise ValueError("same-prompt-hash flag does not match prompt hashes")
        pass_conditions = (
            self.execution_status == "succeeded"
            and self.validation_result == "passed"
            and not same_hash
            and bool(self.required_revisions)
            and bool(self.structured_diff.changes)
            and self.unresolved_p0 == 0
            and self.unresolved_p1 == 0
        )
        if self.passed != pass_conditions:
            raise ValueError("case PASS does not match full-chain acceptance evidence")
        return self


class ReleaseRawResults(_ReleaseModel):
    """Raw result envelope emitted only after all authorized cases execute."""

    schema_version: Literal[1] = 1
    selection_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    q028_flagship_execution: Literal["independent_runs", "shared_run"]
    generated_at: datetime
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    cases: tuple[ReleaseCaseResult, ...] = Field(min_length=5, max_length=5)
    status: Literal["passed", "failed"]

    @model_validator(mode="after")
    def _validate_results(self) -> "ReleaseRawResults":
        _aware(self.generated_at, "generated_at")
        if tuple(item.requirement_label for item in self.cases) != REQUIRED_LABELS:
            raise ValueError("raw results must preserve the authorized case order")
        if any(item.git_sha != self.git_sha for item in self.cases):
            raise ValueError("raw result git SHA does not match case evidence")
        random_runs = [item.run_id for item in self.cases[2:]]
        if len(set(random_runs)) != 3:
            raise ValueError("random cases must produce three distinct run IDs")
        q028_run, flagship_run = self.cases[0].run_id, self.cases[1].run_id
        if self.q028_flagship_execution == "shared_run" and q028_run != flagship_run:
            raise ValueError("shared Q028/flagship evidence must use one run ID")
        if self.q028_flagship_execution == "independent_runs" and q028_run == flagship_run:
            raise ValueError("independent Q028/flagship evidence requires distinct runs")
        expected_status = "passed" if all(item.passed for item in self.cases) else "failed"
        if self.status != expected_status:
            raise ValueError("raw result status does not match case results")
        return self


class Metric004Evidence(_ReleaseModel):
    """The single authorized quantity metric derived from C-007."""

    schema_version: Literal[1] = 1
    metric_id: Literal["T02-METRIC-004"] = "T02-METRIC-004"
    authorized_raw_threshold: Literal["3 个"] = "3 个"
    authorized_value: Literal[3] = 3
    authorized_semantic: Literal["random_case_count"] = "random_case_count"
    random_case_required: Literal[3] = 3
    random_case_executed: int = Field(ge=0)
    random_case_passed: int = Field(ge=0)
    selection_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_results_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    passed: bool

    @model_validator(mode="after")
    def _validate_metric(self) -> "Metric004Evidence":
        if self.random_case_passed > self.random_case_executed:
            raise ValueError("passed random count cannot exceed executed count")
        expected = self.random_case_executed == 3 and self.random_case_passed == 3
        if self.passed != expected:
            raise ValueError("METRIC-004 PASS does not match the authorized count")
        return self


class RegressionMatrixRow(_ReleaseModel):
    schema_version: Literal[1] = 1
    label: RequirementLabel
    question_id: str
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str
    v1_version_id: str
    v2_version_id: str
    v1_prompt_hash: PromptHash
    v2_prompt_hash: PromptHash
    reviewer_issue_count: int = Field(ge=0)
    structured_diff_present: bool
    closure_status: Literal["closed", "open"]
    p0_open_count: int = Field(ge=0)
    p1_open_count: int = Field(ge=0)
    stop_reason: str | None = None
    execution_result: str
    validation_result: str
    artifact_paths: tuple[str, ...]
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    result: Literal["PASS", "FAIL"]

    @classmethod
    def from_result(cls, result: ReleaseCaseResult) -> "RegressionMatrixRow":
        return cls(
            label=result.requirement_label,
            question_id=result.question_id,
            input_hash=result.input_hash,
            run_id=result.run_id,
            v1_version_id=result.v1_version_id,
            v2_version_id=result.v2_version_id,
            v1_prompt_hash=result.v1_prompt_hash,
            v2_prompt_hash=result.v2_prompt_hash,
            reviewer_issue_count=len(result.issue_closures),
            structured_diff_present=bool(result.structured_diff.changes),
            closure_status=(
                "closed"
                if result.unresolved_p0 == 0 and result.unresolved_p1 == 0
                else "open"
            ),
            p0_open_count=result.unresolved_p0,
            p1_open_count=result.unresolved_p1,
            stop_reason=result.stop_reason,
            execution_result=result.execution_status,
            validation_result=result.validation_result,
            artifact_paths=result.evidence_provenance,
            git_sha=result.git_sha,
            result="PASS" if result.passed else "FAIL",
        )


class ReleaseRegressionMatrix(_ReleaseModel):
    schema_version: Literal[1] = 1
    source_raw_results_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    rows: tuple[RegressionMatrixRow, ...] = Field(min_length=5, max_length=5)
    passed: bool

    @model_validator(mode="after")
    def _validate_matrix(self) -> "ReleaseRegressionMatrix":
        if tuple(row.label for row in self.rows) != REQUIRED_LABELS:
            raise ValueError("regression matrix must preserve the required case order")
        if any(row.git_sha != self.git_sha for row in self.rows):
            raise ValueError("matrix git SHA does not match row evidence")
        expected = all(row.result == "PASS" for row in self.rows)
        if self.passed != expected:
            raise ValueError("matrix PASS does not match its rows")
        return self


class CaseExecutor(Protocol):
    def __call__(self, case: ReleaseCaseSelection) -> ReleaseCaseResult: ...


AuthorizationVerifier = Callable[[CaptainCaseAuthorization], None]
CanonicalInputVerifier = Callable[[ReleaseCaseSelection], None]


class T02WaveCReleaseHarness:
    """Execute only a structurally and externally authorized five-case manifest."""

    def __init__(
        self,
        manifest: ReleaseSelectionManifest | Mapping[str, Any],
        *,
        authorization_verifier: AuthorizationVerifier,
        canonical_input_verifier: CanonicalInputVerifier,
        executor: CaseExecutor,
    ) -> None:
        self.manifest = ReleaseSelectionManifest.model_validate(manifest)
        self._authorization_verifier = authorization_verifier
        self._canonical_input_verifier = canonical_input_verifier
        self._executor = executor

    def run(self) -> ReleaseRawResults:
        # Verify every authority/input boundary before invoking any paid or mutable work.
        self._authorization_verifier(self.manifest.authorization)
        for case in self.manifest.cases:
            self._canonical_input_verifier(case)

        results: list[ReleaseCaseResult] = []
        for case in self.manifest.cases:
            result = ReleaseCaseResult.model_validate(self._executor(case))
            if (
                result.requirement_label != case.requirement_label
                or result.question_id != case.question_id
                or result.input_hash != case.input_hash
                or result.canonical_input != case.canonical_input
                or result.git_sha != self.manifest.git_sha
            ):
                raise ValueError("executor result identity does not match selection manifest")
            results.append(result)

        return ReleaseRawResults(
            selection_manifest_sha256=canonical_sha256(
                self.manifest.model_dump(mode="json")
            ),
            q028_flagship_execution=(
                self.manifest.authorization.q028_flagship_execution
            ),
            generated_at=datetime.now(timezone.utc),
            git_sha=self.manifest.git_sha,
            cases=tuple(results),
            status="passed" if all(item.passed for item in results) else "failed",
        )


def build_metric004_evidence(raw: ReleaseRawResults) -> Metric004Evidence:
    random_cases = raw.cases[2:]
    return Metric004Evidence(
        random_case_executed=len(random_cases),
        random_case_passed=sum(item.passed for item in random_cases),
        selection_manifest_sha256=raw.selection_manifest_sha256,
        raw_results_sha256=canonical_sha256(raw.model_dump(mode="json")),
        git_sha=raw.git_sha,
        passed=len(random_cases) == 3 and all(item.passed for item in random_cases),
    )


def build_regression_matrix(raw: ReleaseRawResults) -> ReleaseRegressionMatrix:
    rows = tuple(RegressionMatrixRow.from_result(item) for item in raw.cases)
    return ReleaseRegressionMatrix(
        source_raw_results_sha256=canonical_sha256(raw.model_dump(mode="json")),
        git_sha=raw.git_sha,
        rows=rows,
        passed=all(row.result == "PASS" for row in rows),
    )


class FormalRunFailure(_ReleaseModel):
    """Secret-free failure evidence for a blocked or failed formal attempt."""

    stage: str = Field(min_length=1)
    error_type: str = Field(min_length=1)
    message: str = Field(min_length=1)
    stdout: str = ""
    stderr: str = ""
    state: dict[str, Any]
    artifact_paths: tuple[str, ...] = ()


class FormalActualRunRecord(_ReleaseModel):
    """One unique actual-run record; Q028/FLAGSHIP occupies one record only."""

    schema_version: Literal[1] = 1
    case_key: str = Field(min_length=1)
    requirement_labels: tuple[str, ...] = Field(min_length=1)
    question_id: str = Field(pattern=r"^Q[0-9]{3}$")
    canonical_input: dict[str, Any]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    shared_run: bool
    seed: Literal[FORMAL_RANDOM_SEED] = FORMAL_RANDOM_SEED
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    config: dict[str, Any]
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_mode: Literal["real"] = "real"
    mock_mode: Literal[False] = False
    status: Literal["SUCCEEDED", "RUN_FAILED", "CASE_BLOCKED"]
    actual_run_id: str | None = None
    job_id: str | None = None
    provider: str | None = None
    model: str | None = None
    actual_execution: bool | None = None
    started_at: datetime
    ended_at: datetime
    llm_call_count: int = Field(default=0, ge=0)
    v1_version_id: str | None = None
    v2_version_id: str | None = None
    v1_prompt_hash: str | None = None
    v2_prompt_hash: str | None = None
    reviewer_issues: tuple[dict[str, Any], ...] = ()
    feedback_fingerprint: str | None = None
    revision_context_fingerprint: str | None = None
    revision_context: dict[str, Any] | None = None
    structured_diff: dict[str, Any] | None = None
    diff_hash: str | None = None
    score_before: dict[str, float] = Field(default_factory=dict)
    score_after: dict[str, float] = Field(default_factory=dict)
    score_delta: dict[str, float] = Field(default_factory=dict)
    issue_closures: tuple[dict[str, Any], ...] = ()
    lineage: dict[str, Any] | None = None
    lineage_hash: str | None = None
    stop_reason: str | None = None
    unresolved_p0: int | None = Field(default=None, ge=0)
    unresolved_p1: int | None = Field(default=None, ge=0)
    validation_status: str | None = None
    execution_status: str
    artifact_paths: tuple[str, ...] = ()
    artifact_checksums: dict[str, str] = Field(default_factory=dict)
    failure: FormalRunFailure | None = None
    result: Literal["PASS", "FAIL"]

    @model_validator(mode="after")
    def _validate_formal_run(self) -> "FormalActualRunRecord":
        if self.ended_at < self.started_at:
            raise ValueError("formal run ended_at cannot precede started_at")
        if canonical_sha256(self.canonical_input) != self.input_hash:
            raise ValueError("formal run input hash does not match canonical input")
        if canonical_sha256(self.config) != self.config_hash:
            raise ValueError("formal run config hash does not match config")
        expected = next(
            (item for item in FORMAL_CASE_SPECS if item[0] == self.case_key),
            None,
        )
        if expected is None:
            raise ValueError("formal run case_key is not frozen")
        _, question_id, labels, shared = expected
        if (
            self.question_id != question_id
            or self.requirement_labels != labels
            or self.shared_run != shared
        ):
            raise ValueError("formal run identity does not match frozen case set")
        if self.status != "SUCCEEDED":
            if self.failure is None or self.result != "FAIL":
                raise ValueError("blocked/failed formal run requires failure evidence")
            return self
        if not self.actual_run_id or not self.provider or not self.model:
            raise ValueError("successful formal run requires real run/provider/model identity")
        if self.llm_call_count < 1 or not self.artifact_checksums:
            raise ValueError("successful formal run requires real calls and artifacts")
        complete_revision = all(
            (
                self.v1_version_id,
                self.v2_version_id,
                self.v1_prompt_hash,
                self.v2_prompt_hash,
                self.feedback_fingerprint,
                self.revision_context_fingerprint,
                self.revision_context,
                self.structured_diff,
                self.diff_hash,
                self.lineage,
                self.lineage_hash,
            )
        )
        expected_pass = bool(
            complete_revision
            and self.v1_prompt_hash != self.v2_prompt_hash
            and self.unresolved_p0 == 0
            and self.unresolved_p1 == 0
            and self.validation_status
            and self.execution_status == "succeeded"
        )
        if self.result != ("PASS" if expected_pass else "FAIL"):
            raise ValueError("formal run result contradicts full-chain evidence")
        return self


class FormalRawResults(_ReleaseModel):
    """Exactly four unique records covering five logical obligations."""

    schema_version: Literal[1] = 1
    acceptance_status: Literal["FORMAL"] = "FORMAL"
    captain_authorized: Literal[True] = True
    selection_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    logical_case_count: Literal[5] = 5
    unique_actual_run_count_expected: Literal[4] = 4
    records: tuple[FormalActualRunRecord, ...] = Field(min_length=4, max_length=4)
    actual_run_count: int = Field(ge=0, le=4)
    passed_run_count: int = Field(ge=0, le=4)
    status: Literal["PASS", "FAIL", "BLOCKED"]

    @model_validator(mode="after")
    def _validate_raw_results(self) -> "FormalRawResults":
        if tuple(record.case_key for record in self.records) != tuple(
            item[0] for item in FORMAL_CASE_SPECS
        ):
            raise ValueError("formal raw results must preserve frozen unique-run order")
        run_ids = [record.actual_run_id for record in self.records if record.actual_run_id]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("unique formal records cannot reuse an actual run ID")
        actual_count = len(run_ids)
        passed_count = sum(record.result == "PASS" for record in self.records)
        if (self.actual_run_count, self.passed_run_count) != (
            actual_count,
            passed_count,
        ):
            raise ValueError("formal raw result counters do not match records")
        expected_status = (
            "PASS"
            if passed_count == 4
            else "BLOCKED"
            if any(record.status == "CASE_BLOCKED" for record in self.records)
            else "FAIL"
        )
        if self.status != expected_status:
            raise ValueError("formal raw result status does not match records")
        return self


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _git_output(*args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return process.stdout.strip()


def _current_git_sha() -> str:
    value = _git_output("rev-parse", "HEAD")
    if len(value) != 40:
        raise ValueError("current Git SHA is not a full commit identity")
    return value


def verify_captain_authority() -> dict[str, Any]:
    """Read and validate the Captain confirmation directly from GitHub."""

    process = subprocess.run(
        [
            "gh",
            "api",
            (
                "repos/sage125-ai-scientist-team/SAGE125-AI-Scientist/"
                f"issues/comments/{CAPTAIN_COMMENT_ID}"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(process.stdout)
    body = str(payload.get("body") or "")
    required = (
        "RANDOM_CASE_IDS=[Q095,Q045,Q100]",
        "RANDOM_CASE_SEED=20260814",
        "Q028_FLAGSHIP_SHARED_RUN_ALLOWED=YES",
        "METRIC004_RANDOM_CASE_COUNT_CONFIRMED=YES",
        "C007_LOGICAL_CASE_OBLIGATIONS=5",
        "C007_UNIQUE_ACTUAL_RUNS=4",
        "AUTHORIZED_BY_CAPTAIN=YES",
    )
    if payload.get("user", {}).get("login") != CAPTAIN_LOGIN:
        raise ValueError("Captain confirmation publisher does not match liuyanbo12")
    missing = [token for token in required if token not in body]
    if missing:
        raise ValueError(f"Captain confirmation is missing frozen fields: {missing}")
    if payload.get("html_url") != CAPTAIN_AUTHORITY_URL:
        raise ValueError("Captain confirmation URL does not match frozen authority URL")
    return {
        "url": CAPTAIN_AUTHORITY_URL,
        "original_authority_url": CAPTAIN_ORIGINAL_AUTHORITY_URL,
        "login": CAPTAIN_LOGIN,
        "timestamp": payload["created_at"],
        "verified": True,
        "verified_fields": list(required),
    }


def load_canonical_catalog(source_pdf: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rebuild the canonical 125-question catalog in memory from the official PDF."""

    resolved = source_pdf.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"canonical source PDF is missing: {resolved}")
    source_hash = _sha256_path(resolved)
    if source_hash != SOURCE_DOCUMENT_SHA256:
        raise ValueError("canonical source PDF checksum does not match flagship authority")
    import scripts.extract_125_questions as extractor

    previous_path = extractor.PDF_PATH
    extractor.PDF_PATH = resolved
    try:
        raw = extractor.extract_raw_questions()
        repairs = extractor.repair_known_layout_anomalies(raw)
        unique, removed = extractor.deduplicate_questions(raw)
        fallback = extractor.ensure_pandemic(unique)
        items = extractor.build_question_items(unique, fallback)
        issues = extractor.validate_question_items(items)
    finally:
        extractor.PDF_PATH = previous_path
    if len(items) != 125 or issues:
        raise ValueError(
            f"canonical question extraction failed: count={len(items)}, issues={issues}"
        )
    expected_ids = [f"Q{index:03d}" for index in range(1, 126)]
    if [item["id"] for item in items] != expected_ids:
        raise ValueError("canonical question IDs are not contiguous Q001-Q125")
    provenance = {
        "source_document_url": SOURCE_DOCUMENT_URL,
        "source_document_filename": resolved.name,
        "source_document_sha256": source_hash,
        "source_catalog_sha256": canonical_sha256(items),
        "source_record_count": len(items),
        "removed_count": len(removed),
        "fallback_used": fallback,
        "layout_repairs": list(dict.fromkeys(repairs)),
        "quality_issues": issues,
    }
    return items, provenance


def reproduce_random_selection(items: Sequence[Mapping[str, Any]]) -> list[str]:
    """Apply the exact Captain-frozen population, exclusion, seed, and algorithm."""

    import random

    population = sorted(str(item["id"]) for item in items if item["id"] != "Q028")
    if len(population) != 124:
        raise ValueError("random population must contain Q001-Q125 excluding Q028")
    selected = random.Random(FORMAL_RANDOM_SEED).sample(population, 3)
    if selected != list(FORMAL_RANDOM_CASE_IDS):
        raise ValueError(
            f"RANDOM_SELECTION_REPRODUCIBLE=NO: observed={selected}, "
            f"expected={list(FORMAL_RANDOM_CASE_IDS)}"
        )
    return selected


def _release_config() -> dict[str, Any]:
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "provider": settings.llm_provider,
        "models": {
            "fast": settings.qwen_fast_model,
            "balanced": settings.qwen_balanced_model,
            "strong": settings.qwen_strong_model,
        },
        "use_local_rag": False,
        "use_deep_research": False,
        "use_open_literature": True,
        "reviewer_auto_revision": True,
        "mock_mode": False,
        "random_seed": FORMAL_RANDOM_SEED,
    }


def _artifact_inventory(run_dir: Path) -> tuple[tuple[str, ...], dict[str, str]]:
    if not run_dir.is_dir():
        return (), {}
    files = sorted(path for path in run_dir.rglob("*") if path.is_file())
    paths = tuple(path.as_posix() for path in files)
    checksums = {path.as_posix(): _sha256_path(path) for path in files}
    return paths, checksums


@contextlib.contextmanager
def _temporary_environment(**updates: str):
    original = {name: os.environ.get(name) for name in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _consumer_from_trace(
    run_id: str,
    revision_trace: Mapping[str, Any],
) -> tuple[Any, Any, Any]:
    from app.workflow.explainable_revision import (
        ExplainableRevisionAudit,
        StructuredRevisionDiff,
        build_experiment_revision_context,
    )
    from app.workflow.revision_consumer import (
        RevisionConsumerRecord,
        RevisionConsumerStore,
        VersionDiffEnvelope,
    )
    from app.workflow.revision_recovery import RevisionRecoveryCheckpoint

    checkpoint = RevisionRecoveryCheckpoint.model_validate(
        revision_trace["revision_recovery_checkpoint"]
    )
    audit = ExplainableRevisionAudit.model_validate(revision_trace["revision_audit"])
    if len(checkpoint.versions) != 2:
        raise ValueError("formal C007 run did not produce canonical V1/V2")
    first, second = checkpoint.versions
    context = build_experiment_revision_context(
        previous_version=first,
        unresolved_issues=[issue for issue in first.issue_closures if issue.status == "open"],
        failure_reasons=audit.failure_reasons,
    )
    diff = StructuredRevisionDiff.from_audit(audit)
    lineage_payload = {
        "schema_version": 1,
        "run_id": run_id,
        "versions": [
            {
                "version_id": version.version_id,
                "version_number": version.version_number,
                "parent_version_id": version.parent_version_id,
            }
            for version in checkpoint.versions
        ],
    }
    record = RevisionConsumerRecord(
        run_id=run_id,
        job_id=f"{run_id}:wave-c-release",
        plan_versions=checkpoint.versions,
        revision_context=context,
        revision_audit=audit,
        revision_control=checkpoint.controller,
        version_diffs=(
            VersionDiffEnvelope(
                source_version_id=first.version_id,
                target_version_id=second.version_id,
                diff=diff,
                diff_hash=diff.fingerprint(),
            ),
        ),
        lineage_hash=canonical_sha256(lineage_payload),
    )
    store = RevisionConsumerStore((record,))
    return store, record, context


def _call_dict(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)


def _masked(value: Any) -> Any:
    """Recursively mask secret-like strings before persisting formal evidence."""

    from app.core.logging import mask_text

    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, Mapping):
        return {str(key): _masked(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_masked(item) for item in value]
    return value


def execute_formal_case(
    *,
    case_spec: tuple[str, str, tuple[str, ...], bool],
    canonical_input: dict[str, Any],
    questions_path: Path,
    git_sha: str,
    config: dict[str, Any],
) -> FormalActualRunRecord:
    """Execute one real pipeline case and derive all evidence from its trace."""

    from app.core.config import get_settings
    from app.workflow.artifacts import resolve_artifact_base
    from app.workflow.pipeline import run_pipeline_with_state

    case_key, question_id, labels, shared = case_spec
    started = datetime.now(timezone.utc)
    run_id: str | None = None
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    try:
        with (
            _temporary_environment(SAGE_QUESTIONS_PATH=str(questions_path.resolve())),
            contextlib.redirect_stdout(captured_stdout),
            contextlib.redirect_stderr(captured_stderr),
        ):
            plan, state = run_pipeline_with_state(
                question_id,
                use_local_rag=False,
                use_deep_research=False,
                use_open_literature=True,
                reviewer_auto_revision=True,
                mock_mode=False,
            )
        ended = datetime.now(timezone.utc)
        run_id = state.run_id
        run_dir = resolve_artifact_base(get_settings().export_dir) / run_id
        artifact_paths, artifact_checksums = _artifact_inventory(run_dir)
        calls = [_call_dict(item) for item in state.llm_calls]
        real_calls = [
            item
            for item in calls
            if not item.get("mock") and item.get("provider") != "mock"
        ]
        if state.mock_mode or state.run_mode != "real" or not real_calls:
            raise ValueError("formal actual run lacks non-mock provider call evidence")
        revision_trace = next(
            (item for item in state.agent_trace if item.get("revision_audit")),
            None,
        )
        if revision_trace is None:
            raise ValueError("formal C007 run did not enter a Reviewer-driven V2")
        store, record, context = _consumer_from_trace(run_id, revision_trace)
        versions = store.list_plan_versions(run_id=run_id)
        first, second = versions
        diff = store.get_version_diff(second.version_id)
        issues = store.get_reviewer_issues(run_id=run_id)
        closures = store.get_issue_closures(run_id=run_id)
        open_issues = store.get_open_p0_p1(run_id=run_id)
        p0 = sum(issue.priority == "P0" for issue in open_issues)
        p1 = sum(issue.priority == "P1" for issue in open_issues)
        scores = store.get_score_deltas(second.version_id)
        lineage = store.get_lineage(run_id=run_id)
        v1_hash = first.prompt_fingerprints["experiment_designer"]
        v2_hash = second.prompt_fingerprints["experiment_designer"]
        audit = record.revision_audit
        assert audit is not None
        validation_ok = bool(
            audit.accepted
            and v1_hash != v2_hash
            and p0 == 0
            and p1 == 0
            and artifact_checksums
        )
        first_call = real_calls[0]
        provider = str(first_call.get("provider") or config["provider"])
        model = str(
            first_call.get("model")
            or first_call.get("model_name_internal")
            or config["models"]["fast"]
        )
        failure = None
        if not validation_ok:
            failure = FormalRunFailure(
                stage="full_chain_validation",
                error_type="C007AcceptanceBlocked",
                message="real run completed but V1/V2 closure gates did not all pass",
                stdout=str(_masked(captured_stdout.getvalue())),
                stderr=str(_masked(captured_stderr.getvalue())),
                state={
                    "audit_accepted": audit.accepted,
                    "prompt_hash_changed": v1_hash != v2_hash,
                    "unresolved_p0": p0,
                    "unresolved_p1": p1,
                },
                artifact_paths=artifact_paths,
            )
        return FormalActualRunRecord(
            case_key=case_key,
            requirement_labels=labels,
            question_id=question_id,
            canonical_input=canonical_input,
            input_hash=canonical_sha256(canonical_input),
            shared_run=shared,
            git_sha=git_sha,
            config=config,
            config_hash=canonical_sha256(config),
            status="SUCCEEDED",
            actual_run_id=run_id,
            job_id=record.job_id,
            provider=provider,
            model=model,
            actual_execution=bool(plan.actual_execution),
            started_at=started,
            ended_at=ended,
            llm_call_count=len(real_calls),
            v1_version_id=first.version_id,
            v2_version_id=second.version_id,
            v1_prompt_hash=v1_hash,
            v2_prompt_hash=v2_hash,
            reviewer_issues=tuple(issue.model_dump(mode="json") for issue in issues),
            feedback_fingerprint=canonical_sha256(
                first.review_feedback.model_dump(mode="json")
            ),
            revision_context_fingerprint=canonical_sha256(
                context.model_dump(mode="json")
            ),
            revision_context=context.model_dump(mode="json"),
            structured_diff=diff.diff.model_dump(mode="json"),
            diff_hash=diff.diff_hash,
            score_before={name: item.before for name, item in scores.items()},
            score_after={name: item.after for name, item in scores.items()},
            score_delta={name: item.delta for name, item in scores.items()},
            issue_closures=tuple(item.model_dump(mode="json") for item in closures),
            lineage=lineage.model_dump(mode="json"),
            lineage_hash=lineage.lineage_hash,
            stop_reason=store.get_stop_reason(run_id=run_id),
            unresolved_p0=p0,
            unresolved_p1=p1,
            validation_status=str(plan.validation_status),
            execution_status="succeeded",
            artifact_paths=artifact_paths,
            artifact_checksums=artifact_checksums,
            failure=failure,
            result="PASS" if validation_ok else "FAIL",
        )
    except Exception as exc:
        ended = datetime.now(timezone.utc)
        run_id = run_id or getattr(exc, "run_id", None)
        run_dir = (
            resolve_artifact_base(get_settings().export_dir) / run_id
            if run_id
            else Path("__missing_run__")
        )
        artifact_paths, artifact_checksums = _artifact_inventory(run_dir)
        return FormalActualRunRecord(
            case_key=case_key,
            requirement_labels=labels,
            question_id=question_id,
            canonical_input=canonical_input,
            input_hash=canonical_sha256(canonical_input),
            shared_run=shared,
            git_sha=git_sha,
            config=config,
            config_hash=canonical_sha256(config),
            status="RUN_FAILED",
            actual_run_id=run_id,
            started_at=started,
            ended_at=ended,
            execution_status="failed",
            artifact_paths=artifact_paths,
            artifact_checksums=artifact_checksums,
            failure=FormalRunFailure(
                stage="pipeline_execution",
                error_type=type(exc).__name__,
                message=str(_masked(str(exc))),
                stdout=str(_masked(captured_stdout.getvalue())),
                stderr=str(_masked(captured_stderr.getvalue())),
                state={"question_id": question_id, "run_id": run_id},
                artifact_paths=artifact_paths,
            ),
            result="FAIL",
        )


def _blocked_record(
    *,
    case_spec: tuple[str, str, tuple[str, ...], bool],
    canonical_input: dict[str, Any],
    git_sha: str,
    config: dict[str, Any],
    preflight: Mapping[str, Any],
    preflight_path: Path,
) -> FormalActualRunRecord:
    case_key, question_id, labels, shared = case_spec
    now = datetime.now(timezone.utc)
    return FormalActualRunRecord(
        case_key=case_key,
        requirement_labels=labels,
        question_id=question_id,
        canonical_input=canonical_input,
        input_hash=canonical_sha256(canonical_input),
        shared_run=shared,
        git_sha=git_sha,
        config=config,
        config_hash=canonical_sha256(config),
        status="CASE_BLOCKED",
        started_at=now,
        ended_at=now,
        execution_status="blocked_before_provider_call",
        artifact_paths=(preflight_path.as_posix(),),
        artifact_checksums={preflight_path.as_posix(): _sha256_path(preflight_path)},
        failure=FormalRunFailure(
            stage="provider_preflight",
            error_type="RealProviderPreflightBlocked",
            message="; ".join(str(item) for item in preflight.get("errors", ())),
            state=dict(preflight),
            artifact_paths=(preflight_path.as_posix(),),
        ),
        result="FAIL",
    )


def _logical_matrix_rows(records: Sequence[FormalActualRunRecord]) -> list[dict[str, Any]]:
    by_label = {
        label: record
        for record in records
        for label in record.requirement_labels
    }
    rows: list[dict[str, Any]] = []
    for label in FORMAL_LOGICAL_LABELS:
        record = by_label[label]
        rows.append(
            {
                "requirement_label": label,
                "question_id": record.question_id,
                "run_id": record.actual_run_id,
                "shared_run": record.shared_run,
                "input_hash": record.input_hash,
                "config_hash": record.config_hash,
                "seed": record.seed,
                "git_sha": record.git_sha,
                "v1_version_id": record.v1_version_id,
                "v2_version_id": record.v2_version_id,
                "v1_prompt_hash": record.v1_prompt_hash,
                "v2_prompt_hash": record.v2_prompt_hash,
                "reviewer_issues": list(record.reviewer_issues),
                "structured_diff": record.structured_diff,
                "issue_closures": list(record.issue_closures),
                "unresolved_p0": record.unresolved_p0,
                "unresolved_p1": record.unresolved_p1,
                "stop_reason": record.stop_reason,
                "execution": record.execution_status,
                "validation": record.validation_status,
                "artifact_paths": list(record.artifact_paths),
                "artifact_checksums": record.artifact_checksums,
                "result": record.result,
            }
        )
    return rows


def _write_matrix_markdown(path: Path, matrix: Mapping[str, Any]) -> None:
    lines = [
        "# T02 Wave C C-008 regression matrix",
        "",
        f"- LOGICAL_CASE_COUNT={matrix['logical_case_count']}",
        f"- UNIQUE_ACTUAL_RUN_COUNT={matrix['unique_actual_run_count']}",
        f"- RESULT={matrix['result']}",
        "",
        "| Label | QID | Run ID | Shared | Execution | P0 | P1 | Result |",
        "|---|---|---|---:|---|---:|---:|---|",
    ]
    for row in matrix["rows"]:
        lines.append(
            "| {requirement_label} | {question_id} | {run_id} | {shared_run} | "
            "{execution} | {unresolved_p0} | {unresolved_p1} | {result} |".format(
                **row
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _write_reproduction(path: Path, preflight: Mapping[str, Any]) -> None:
    """Write commands that invoke the same fail-closed formal code path."""

    errors = list(preflight.get("errors", ()))
    status = "PASS" if preflight.get("ok") else "CASE_BLOCKED"
    error_lines = (
        [f"- `{str(_masked(item))}`" for item in errors]
        if errors
        else ["- None."]
    )
    lines = [
        "# T02 Wave C formal reproduction",
        "",
        "This procedure has no mock, fixture, synthetic-result, or case-substitution path.",
        "The command exits `0` only when all four unique real runs and every gate pass;",
        "it exits `3` after writing truthful evidence when any case is blocked or fails.",
        "",
        "## Prerequisites",
        "",
        "Run from the repository root on `t02/c-revision-hardening`. Configure the real",
        "DashScope workspace/provider credentials through the repository-supported `.env`",
        "mechanism; never place secrets in these artifacts.",
        "",
        "```powershell",
        "$sourcePdf = 'data/raw/sjtu-booklet.pdf'",
        f"Invoke-WebRequest -Uri '{SOURCE_DOCUMENT_URL}' -OutFile $sourcePdf",
        "(Get-FileHash -Algorithm SHA256 $sourcePdf).Hash.ToLowerInvariant()",
        "```",
        "",
        f"The required SHA-256 is `{SOURCE_DOCUMENT_SHA256}`.",
        "",
        "## 1. Reproduce the frozen random selection",
        "",
        "```powershell",
        "python -c \"import random; p=[f'Q{i:03d}' for i in range(1,126) if i != 28]; print(random.Random(20260814).sample(sorted(p),3))\"",
        "```",
        "",
        "Expected: `['Q095', 'Q045', 'Q100']`.",
        "",
        "## 2-10. Run and aggregate the formal release",
        "",
        "The runner intentionally performs these operations atomically and in order:",
        "Q028/FLAGSHIP shared run, Q095, Q045, Q100, raw-result aggregation,",
        "METRIC-004 computation, five-row regression matrix generation, prompt-hash",
        "audit, and P0/P1 closure audit. This prevents duplicated Q028 evidence or",
        "aggregation from a partial/mixed run set.",
        "",
        "```powershell",
        "python -m app.workflow.wave_c_release --execute-release --source-pdf $sourcePdf --output-dir docs/modules/T02/wave_c_release",
        "```",
        "",
        "The four cases are always executed in frozen order and every call uses",
        "`mock_mode=False`. A failed preflight creates four `CASE_BLOCKED` records and",
        "does not invoke a mock fallback. A failed case is retained and never replaced.",
        "",
        "Inspect the generated evidence with real shell commands:",
        "",
        "```powershell",
        "Get-Content docs/modules/T02/wave_c_release/raw_results.json",
        "Get-Content docs/modules/T02/wave_c_release/metrics.json",
        "Get-Content docs/modules/T02/wave_c_release/regression_matrix.json",
        "Get-Content docs/modules/T02/wave_c_release/prompt_hash_audit.json",
        "Get-Content docs/modules/T02/wave_c_release/p0_p1_closure.json",
        "Get-Content docs/modules/T02/wave_c_release/checksums.json",
        "```",
        "",
        "## Recorded preflight result",
        "",
        f"`PROVIDER_PREFLIGHT={status}`",
        "",
        *error_lines,
        "",
        "Provider preflight details are generated by `app.workflow.preflight` and",
        "persisted in `provider_preflight.json`; the values above are not hand-filled",
        "acceptance results.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run_formal_release(source_pdf: Path, output_dir: Path) -> dict[str, Any]:
    """Run selection, preflight, four unique real runs, and evidence aggregation."""

    from app.workflow.preflight import run_real_preflight

    authority = verify_captain_authority()
    git_sha = _current_git_sha()
    items, source = load_canonical_catalog(source_pdf)
    selected = reproduce_random_selection(items)
    by_id = {str(item["id"]): dict(item) for item in items}
    flagship = json.loads(Path(FLAGSHIP_SOURCE).read_text(encoding="utf-8"))
    if flagship.get("question_id") != "Q028":
        raise ValueError("flagship selection manifest is not Q028")
    if canonical_sha256(by_id["Q028"]) != Q028_CANONICAL_INPUT_HASH:
        raise ValueError("Q028 canonical input hash does not match frozen authority")

    output_dir.mkdir(parents=True, exist_ok=True)
    selection = {
        "schema_version": "t02-wave-c-selection-v1",
        "acceptance_status": "FORMAL",
        "captain_authorized": True,
        "captain_authority": authority,
        "authority_source": AUTHORITY_SOURCE,
        "authority_commit": AUTHORITY_COMMIT,
        "git_sha": git_sha,
        "canonical_catalog_count": 125,
        "population": [
            f"Q{index:03d}" for index in range(1, 126) if index != 28
        ],
        "population_count": 124,
        "population_semantic": (
            "canonical Q001-Q125 normalized sorted, excluding Q028"
        ),
        "excluded": ["Q028"],
        "algorithm": SELECTION_ALGORITHM,
        "seed": FORMAL_RANDOM_SEED,
        "selected": selected,
        "random_selection_reproducible": True,
        "logical_case_obligations": 5,
        "logical_labels": list(FORMAL_LOGICAL_LABELS),
        "unique_actual_runs": 4,
        "q028_flagship_shared_run_allowed": True,
        "cases": [
            {
                "case_key": key,
                "question_id": qid,
                "requirement_labels": list(labels),
                "shared_run": shared,
                "input_hash": canonical_sha256(by_id[qid]),
            }
            for key, qid, labels, shared in FORMAL_CASE_SPECS
        ],
    }
    selection_path = output_dir / "selection_manifest.json"
    _write_json(selection_path, selection)
    dataset = {
        "schema_version": "t02-wave-c-dataset-v1",
        "acceptance_status": "FORMAL",
        "captain_authorized": True,
        "git_sha": git_sha,
        "selection_manifest_sha256": _sha256_path(selection_path),
        **source,
        "canonical_source_path": "data/raw/sjtu-booklet.pdf (external; not committed)",
        "selected_records": [by_id[qid] for qid in ("Q028", *FORMAL_RANDOM_CASE_IDS)],
        "selected_record_hashes": {
            qid: canonical_sha256(by_id[qid])
            for qid in ("Q028", *FORMAL_RANDOM_CASE_IDS)
        },
        "flagship_manifest": FLAGSHIP_SOURCE,
        "flagship_question_id": "Q028",
    }
    _write_json(output_dir / "dataset_manifest.json", dataset)

    config = _release_config()
    preflight = _masked(
        run_real_preflight(
            use_local_rag=False,
            use_deep_research=False,
            check_connectivity=True,
        )
    )
    preflight_path = output_dir / "provider_preflight.json"
    _write_json(preflight_path, preflight)
    records: list[FormalActualRunRecord] = []
    if not preflight["ok"]:
        records = [
            _blocked_record(
                case_spec=spec,
                canonical_input=by_id[spec[1]],
                git_sha=git_sha,
                config=config,
                preflight=preflight,
                preflight_path=preflight_path,
            )
            for spec in FORMAL_CASE_SPECS
        ]
    else:
        with tempfile.TemporaryDirectory(prefix="t02-wave-c-") as temp_dir:
            questions_path = Path(temp_dir) / "questions_125.json"
            _write_json(questions_path, items)
            records = [
                execute_formal_case(
                    case_spec=spec,
                    canonical_input=by_id[spec[1]],
                    questions_path=questions_path,
                    git_sha=git_sha,
                    config=config,
                )
                for spec in FORMAL_CASE_SPECS
            ]
    raw = FormalRawResults(
        selection_manifest_sha256=_sha256_path(selection_path),
        git_sha=git_sha,
        records=tuple(records),
        actual_run_count=sum(record.actual_run_id is not None for record in records),
        passed_run_count=sum(record.result == "PASS" for record in records),
        status=(
            "PASS"
            if all(record.result == "PASS" for record in records)
            else "BLOCKED"
            if any(record.status == "CASE_BLOCKED" for record in records)
            else "FAIL"
        ),
    )
    raw_path = output_dir / "raw_results.json"
    _write_json(raw_path, raw)

    random_records = [record for record in records if record.question_id != "Q028"]
    random_executed = sum(record.actual_run_id is not None for record in random_records)
    random_passed = sum(record.result == "PASS" for record in random_records)
    metrics = {
        "schema_version": 1,
        "metric_id": "T02-METRIC-004",
        "authorized_raw_threshold": "3 个",
        "authorized_value": 3,
        "authorized_semantic": "random_case_count",
        "random_case_required": 3,
        "random_case_ids": list(FORMAL_RANDOM_CASE_IDS),
        "random_case_selected": 3,
        "random_case_executed": random_executed,
        "random_case_passed": random_passed,
        "selection_manifest_sha256": _sha256_path(selection_path),
        "raw_results_sha256": _sha256_path(raw_path),
        "git_sha": git_sha,
        "result": "PASS" if random_executed == 3 and random_passed == 3 else "FAIL",
    }
    _write_json(output_dir / "metrics.json", metrics)

    matrix_rows = _logical_matrix_rows(records)
    matrix = {
        "schema_version": 1,
        "logical_case_count": 5,
        "unique_actual_run_count": raw.actual_run_count,
        "unique_actual_run_count_expected": 4,
        "q028_flagship_shared_run": True,
        "git_sha": git_sha,
        "source_raw_results_sha256": _sha256_path(raw_path),
        "rows": matrix_rows,
        "result": (
            "PASS"
            if all(row["result"] == "PASS" for row in matrix_rows)
            else "BLOCKED"
            if any(record.status == "CASE_BLOCKED" for record in records)
            else "FAIL"
        ),
    }
    _write_json(output_dir / "regression_matrix.json", matrix)
    _write_matrix_markdown(output_dir / "regression_matrix.md", matrix)

    prompt_rows = []
    for record in records:
        trace_result = (
            "PASS"
            if record.v1_prompt_hash
            and record.v2_prompt_hash
            and record.v1_prompt_hash != record.v2_prompt_hash
            and record.diff_hash
            else "BLOCKED"
            if record.status == "CASE_BLOCKED"
            else "FAIL"
        )
        prompt_rows.append(
            {
                "run_id": record.actual_run_id,
                "requirement_labels": list(record.requirement_labels),
                "question_id": record.question_id,
                "v1_prompt_hash": record.v1_prompt_hash,
                "v2_prompt_hash": record.v2_prompt_hash,
                "feedback_fingerprint": record.feedback_fingerprint,
                "revision_context_fingerprint": record.revision_context_fingerprint,
                "diff_hash": record.diff_hash,
                "false_iteration_detected": (
                    record.v1_prompt_hash == record.v2_prompt_hash
                    if record.v1_prompt_hash and record.v2_prompt_hash
                    else None
                ),
                "trace_evidence": {
                    "reviewer_issue_ids": [
                        issue.get("issue_id") for issue in record.reviewer_issues
                    ],
                    "revision_context_present": record.revision_context is not None,
                    "structured_diff_present": record.structured_diff is not None,
                },
                "trace_result": trace_result,
            }
        )
    evaluated_false_iterations = [
        row["false_iteration_detected"]
        for row in prompt_rows
        if row["false_iteration_detected"] is not None
    ]
    prompt_audit = {
        "schema_version": 1,
        "git_sha": git_sha,
        "records": prompt_rows,
        "false_iteration_count": (
            sum(evaluated_false_iterations) if evaluated_false_iterations else None
        ),
        "result": (
            "PASS_CANDIDATE"
            if len(evaluated_false_iterations) == 4
            and not any(evaluated_false_iterations)
            and all(row["trace_result"] == "PASS" for row in prompt_rows)
            else "BLOCKED"
        ),
    }
    _write_json(output_dir / "prompt_hash_audit.json", prompt_audit)

    closure_rows = [
        {
            "run_id": record.actual_run_id,
            "requirement_labels": list(record.requirement_labels),
            "question_id": record.question_id,
            "reviewer_issues": list(record.reviewer_issues),
            "issue_closures": list(record.issue_closures),
            "unresolved_p0": record.unresolved_p0,
            "unresolved_p1": record.unresolved_p1,
            "result": (
                "PASS"
                if record.unresolved_p0 == 0 and record.unresolved_p1 == 0
                else "BLOCKED"
                if record.status == "CASE_BLOCKED"
                else "FAIL"
            ),
        }
        for record in records
    ]
    closure = {
        "schema_version": 1,
        "git_sha": git_sha,
        "records": closure_rows,
        "unresolved_p0": (
            sum(row["unresolved_p0"] for row in closure_rows)
            if all(row["unresolved_p0"] is not None for row in closure_rows)
            else None
        ),
        "unresolved_p1": (
            sum(row["unresolved_p1"] for row in closure_rows)
            if all(row["unresolved_p1"] is not None for row in closure_rows)
            else None
        ),
        "result": (
            "PASS"
            if all(row["result"] == "PASS" for row in closure_rows)
            else "BLOCKED"
        ),
    }
    _write_json(output_dir / "p0_p1_closure.json", closure)
    _write_reproduction(output_dir / "reproduction.md", preflight)

    primary_names = (
        "selection_manifest.json",
        "dataset_manifest.json",
        "provider_preflight.json",
        "raw_results.json",
        "metrics.json",
        "regression_matrix.json",
        "regression_matrix.md",
        "prompt_hash_audit.json",
        "p0_p1_closure.json",
        "reproduction.md",
    )
    primary_files = [output_dir / name for name in primary_names if (output_dir / name).is_file()]
    artifact_manifest = {
        "schema_version": 1,
        "git_sha": git_sha,
        "artifacts": [
            {
                "path": path.relative_to(output_dir).as_posix(),
                "sha256": _sha256_path(path),
                "size_bytes": path.stat().st_size,
            }
            for path in primary_files
        ],
    }
    artifact_manifest_path = output_dir / "artifact_manifest.json"
    _write_json(artifact_manifest_path, artifact_manifest)
    checksum_files = [*primary_files, artifact_manifest_path]
    checksums = {
        "schema_version": 1,
        "algorithm": "sha256",
        "git_sha": git_sha,
        "files": {
            path.relative_to(output_dir).as_posix(): _sha256_path(path)
            for path in checksum_files
        },
    }
    _write_json(output_dir / "checksums.json", checksums)
    return {
        "git_sha": git_sha,
        "authority": authority,
        "random_selection_reproducible": True,
        "raw_status": raw.status,
        "actual_run_count": raw.actual_run_count,
        "passed_run_count": raw.passed_run_count,
        "random_executed": random_executed,
        "random_passed": random_passed,
        "false_iteration_count": prompt_audit["false_iteration_count"],
        "unresolved_p0": closure["unresolved_p0"],
        "unresolved_p1": closure["unresolved_p1"],
        "blocker": None if raw.status == "PASS" else records[0].failure.message,
    }


def release_schema_bundle() -> dict[str, Any]:
    """Return schemas without creating an evidence or PASS artifact."""

    return {
        "selection_manifest": ReleaseSelectionManifest.model_json_schema(),
        "dataset_manifest": ReleaseDatasetManifest.model_json_schema(),
        "raw_results": ReleaseRawResults.model_json_schema(),
        "metric004": Metric004Evidence.model_json_schema(),
        "regression_matrix": ReleaseRegressionMatrix.model_json_schema(),
    }


def load_selection_manifest(path: Path) -> ReleaseSelectionManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ReleaseSelectionManifest.model_validate(payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate schemas or execute the Captain-authorized T02 Wave C "
            "fail-closed real-run release"
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--print-schema",
        choices=(
            "all",
            "selection_manifest",
            "dataset_manifest",
            "raw_results",
            "metric004",
            "regression_matrix",
        ),
    )
    group.add_argument("--validate-selection", type=Path)
    group.add_argument(
        "--execute-release",
        action="store_true",
        help="verify authority/source, run four unique real cases, and aggregate evidence",
    )
    parser.add_argument(
        "--source-pdf",
        type=Path,
        help="official sjtu-booklet.pdf used to rebuild canonical Q001-Q125",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/modules/T02/wave_c_release"),
        help="formal evidence directory",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.print_schema:
            schemas = release_schema_bundle()
            selected = schemas if args.print_schema == "all" else schemas[args.print_schema]
            print(json.dumps(selected, ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        if args.execute_release:
            if args.source_pdf is None:
                raise ValueError("--source-pdf is required with --execute-release")
            summary = run_formal_release(args.source_pdf, args.output_dir)
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
            return 0 if summary["raw_status"] == "PASS" else 3
        manifest = load_selection_manifest(args.validate_selection)
        print(
            json.dumps(
                {
                    "status": "STRUCTURE_VALID_ONLY",
                    "formal_execution_authorized": False,
                    "authorization_reference": manifest.authorization.reference_url,
                    "case_labels": [case.requirement_label for case in manifest.cases],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        RuntimeError,
        subprocess.CalledProcessError,
        ValidationError,
        ValueError,
    ) as exc:
        print(f"T02_WAVE_C_RELEASE_INPUT_INVALID: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised through the module CLI
    raise SystemExit(main())


__all__ = [
    "CaptainCaseAuthorization",
    "FormalActualRunRecord",
    "FormalRawResults",
    "FormalRunFailure",
    "Metric004Evidence",
    "RegressionMatrixRow",
    "ReleaseDatasetManifest",
    "ReleaseCaseResult",
    "ReleaseCaseSelection",
    "ReleaseRawResults",
    "ReleaseRegressionMatrix",
    "ReleaseSelectionManifest",
    "T02WaveCReleaseHarness",
    "build_metric004_evidence",
    "build_regression_matrix",
    "canonical_sha256",
    "load_selection_manifest",
    "load_canonical_catalog",
    "reproduce_random_selection",
    "release_schema_bundle",
    "run_formal_release",
    "verify_captain_authority",
]
