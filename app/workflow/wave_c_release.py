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
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SkipValidation,
    ValidationError,
    field_validator,
    model_validator,
)

from app.contracts.execution import ExecutionResult
from app.contracts.multimodal import MultimodalArtifact, to_consumer_summary
from app.contracts.revision import IssueClosure, ReviewFeedback
from app.workflow.explainable_revision import (
    ExperimentRevisionContext,
    StructuredRevisionDiff,
)
from app.workflow.revision_feedback import build_revision_feedback
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
PAIRING_AUTHORITY_COMMENT_ID = 5300864125
PAIRING_AUTHORITY_URL = (
    "https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/"
    "pull/37#issuecomment-5300864125"
)
PAIRING_AUTHORITY_BOUND_HEAD = "5380d9a2d0c50db4055faa709499632033e73fa6"
FROZEN_PAIRING_POLICY = "FROZEN_V1"
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
AuthorizedModel = Literal["qwen3.6-flash", "qwen3.7-plus", "qwen3.7-max"]
FrozenModelPolicy = Literal["TIERED_ROUTE_ALLOWED"]
ActualExecutionRequirement = Literal["T05_EXECUTION_RESULT_REQUIRED"]
PairingPolicy = Literal["FROZEN_V1"]
AuthorityCompatibilityPath = Literal["CAPTAIN_EXACT", "LEGACY_ALIAS"]

AUTHORIZED_MODEL_IDENTITIES: tuple[AuthorizedModel, ...] = (
    "qwen3.6-flash",
    "qwen3.7-plus",
    "qwen3.7-max",
)
_AUTHORIZED_MODEL_SET = frozenset(AUTHORIZED_MODEL_IDENTITIES)
_LEGACY_TIERED_MODEL_POLICY = (
    "TIERED_QWEN3_6_FLASH_QWEN3_7_PLUS_QWEN3_7_MAX"
)
_LEGACY_ACTUAL_REQUIREMENT = "T05_T06_MULTIMODAL_REQUIRED"


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


_SECRET_FIELD_FRAGMENTS = ("api_key", "apikey", "password", "secret", "token")
_PATH_FIELD_NAMES = {
    "entrypoint",
    "relative_path",
    "source_path",
    "workspace_relative_path",
    "workspace_uri",
}
_PATH_ANCHORS = ("app/", "artifacts/", "data/", "datasets/", "docs/", "tests/")


def _canonical_path_identity(value: str) -> str:
    """Remove machine-specific absolute roots while preserving stable source identity."""

    normalized = value.strip().replace("\\", "/")
    fragment = ""
    if "#" in normalized:
        normalized, fragment = normalized.split("#", 1)
        fragment = f"#{fragment}"
    lower = normalized.casefold()
    for anchor in _PATH_ANCHORS:
        index = lower.find(anchor)
        if index >= 0:
            return normalized[index:] + fragment
    is_absolute = bool(
        re.match(r"^[a-zA-Z]:/", normalized)
        or normalized.startswith("/")
        or lower.startswith("file://")
    )
    if is_absolute:
        filename = normalized.rstrip("/").rsplit("/", 1)[-1]
        return f"<absolute>/{filename}{fragment}"
    return normalized + fragment


def _canonical_evidence_payload(value: Any, *, field_name: str = "") -> Any:
    """Build a secret-free, path-stable payload for formal evidence hashing."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            lowered = name.casefold()
            if any(fragment in lowered for fragment in _SECRET_FIELD_FRAGMENTS):
                if item not in (None, "", False, [], {}):
                    raise ValueError(
                        f"secret-like field is forbidden in formal hash payload: {name}"
                    )
                continue
            result[name] = _canonical_evidence_payload(item, field_name=name)
        return result
    if isinstance(value, (list, tuple)):
        return [
            _canonical_evidence_payload(item, field_name=field_name)
            for item in value
        ]
    if isinstance(value, str) and field_name in _PATH_FIELD_NAMES:
        return _canonical_path_identity(value)
    return value


def canonical_evidence_sha256(value: Any) -> str:
    """Hash canonical evidence content without secrets or local absolute-root noise."""

    return canonical_sha256(_canonical_evidence_payload(value))


def execution_result_hash(result: ExecutionResult) -> str:
    return canonical_evidence_sha256(result)


def execution_summary_hash(result: ExecutionResult) -> str:
    projection = build_revision_feedback(execution_result=result)
    if projection is None or projection.execution is None:
        raise ValueError("execution summary projection is missing")
    return canonical_evidence_sha256(projection.execution)


def multimodal_artifact_hash(artifact: MultimodalArtifact) -> str:
    return canonical_evidence_sha256(artifact)


def multimodal_consumer_summary_hash(artifact: MultimodalArtifact) -> str:
    return canonical_evidence_sha256(to_consumer_summary(artifact))


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


class FormalAcceptanceAuthority(_ReleaseModel):
    """Captain-controlled acceptance semantics for a formal C007 run."""

    frozen_model_policy: FrozenModelPolicy | None = None
    authorized_models: tuple[AuthorizedModel, ...] = ()
    actual_requirement: ActualExecutionRequirement | None = None
    multimodal_required: bool | None = None
    pairing_policy_reference: PairingPolicy | None = None
    pairing_authority_ready: bool
    pairing_authority_required: bool
    compatibility_path: AuthorityCompatibilityPath
    status: Literal["AUTHORIZED", "BLOCKED_AUTHORITY_REQUIRED"]
    ready: bool
    missing_fields: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_authority(self) -> "FormalAcceptanceAuthority":
        expected_ready = bool(
            self.frozen_model_policy
            and self.authorized_models == AUTHORIZED_MODEL_IDENTITIES
            and self.actual_requirement
            and self.multimodal_required is True
            and self.pairing_policy_reference == FROZEN_PAIRING_POLICY
            and not self.missing_fields
        )
        expected_status = (
            "AUTHORIZED" if expected_ready else "BLOCKED_AUTHORITY_REQUIRED"
        )
        if self.ready != expected_ready or self.status != expected_status:
            raise ValueError("formal acceptance authority state is inconsistent")
        expected_pairing_ready = (
            self.pairing_policy_reference == FROZEN_PAIRING_POLICY
        )
        if (
            self.pairing_authority_ready != expected_pairing_ready
            or self.pairing_authority_required == expected_pairing_ready
        ):
            raise ValueError("pairing authority state is inconsistent")
        return self


def resolve_formal_acceptance_authority(
    authority: Mapping[str, Any],
) -> FormalAcceptanceAuthority:
    """Resolve exact Captain fields, with an explicit legacy compatibility path."""

    raw_model = authority.get("FROZEN_MODEL_POLICY")
    if raw_model is None:
        raw_model = authority.get("frozen_model_policy")
    raw_models = authority.get("AUTHORIZED_MODELS")
    if raw_models is None:
        raw_models = authority.get("authorized_models")
    raw_requirement = authority.get("C007_ACTUAL_REQUIREMENT")
    if raw_requirement is None:
        raw_requirement = authority.get("actual_requirement")
    raw_multimodal = authority.get("T06_MULTIMODAL_EVIDENCE_REQUIRED")
    if raw_multimodal is None:
        raw_multimodal = authority.get("multimodal_required")
    raw_pairing_policy = authority.get("C007_CROSS_OWNER_PAIRING_POLICY")

    compatibility_path: AuthorityCompatibilityPath = "CAPTAIN_EXACT"
    model_policy: FrozenModelPolicy | None = None
    authorized_models: tuple[AuthorizedModel, ...] = ()
    actual_requirement: ActualExecutionRequirement | None = None
    multimodal_required: bool | None = None
    pairing_policy: PairingPolicy | None = None
    missing: list[str] = []

    if raw_model == "TIERED_ROUTE_ALLOWED":
        model_policy = "TIERED_ROUTE_ALLOWED"
    elif raw_model == _LEGACY_TIERED_MODEL_POLICY:
        compatibility_path = "LEGACY_ALIAS"
        model_policy = "TIERED_ROUTE_ALLOWED"
    elif raw_model:
        missing.append("FROZEN_MODEL_POLICY_INVALID")
    else:
        missing.append("FROZEN_MODEL_POLICY")

    if isinstance(raw_models, str):
        parsed_models = tuple(
            item.strip()
            for item in raw_models.strip().strip("[]").split(",")
            if item.strip()
        )
    elif isinstance(raw_models, Sequence) and not isinstance(
        raw_models, (bytes, bytearray)
    ):
        parsed_models = tuple(str(item).strip() for item in raw_models)
    else:
        parsed_models = ()
    if parsed_models:
        if (
            len(parsed_models) == len(AUTHORIZED_MODEL_IDENTITIES)
            and frozenset(parsed_models) == _AUTHORIZED_MODEL_SET
        ):
            authorized_models = AUTHORIZED_MODEL_IDENTITIES
        else:
            missing.append("AUTHORIZED_MODELS_INVALID")
    elif compatibility_path == "LEGACY_ALIAS":
        authorized_models = AUTHORIZED_MODEL_IDENTITIES
    else:
        missing.append("AUTHORIZED_MODELS")

    if raw_requirement == "T05_EXECUTION_RESULT_REQUIRED":
        actual_requirement = "T05_EXECUTION_RESULT_REQUIRED"
    elif raw_requirement:
        missing.append("C007_ACTUAL_REQUIREMENT_INVALID")
    else:
        legacy_requirement = authority.get("C007_ACTUAL_EXECUTION_REQUIREMENT")
        if legacy_requirement is None:
            legacy_requirement = authority.get("actual_execution_requirement")
        if legacy_requirement == _LEGACY_ACTUAL_REQUIREMENT:
            compatibility_path = "LEGACY_ALIAS"
            actual_requirement = "T05_EXECUTION_RESULT_REQUIRED"
            if raw_multimodal is None:
                raw_multimodal = True
        else:
            missing.append("C007_ACTUAL_REQUIREMENT")

    if raw_multimodal is True or (
        isinstance(raw_multimodal, str)
        and raw_multimodal.strip().upper() == "YES"
    ):
        multimodal_required = True
    elif raw_multimodal is False or (
        isinstance(raw_multimodal, str)
        and raw_multimodal.strip().upper() == "NO"
    ):
        multimodal_required = False
        missing.append("T06_MULTIMODAL_EVIDENCE_REQUIRED_INVALID")
    else:
        missing.append("T06_MULTIMODAL_EVIDENCE_REQUIRED")

    if raw_pairing_policy == FROZEN_PAIRING_POLICY:
        pairing_policy = FROZEN_PAIRING_POLICY
    elif raw_pairing_policy:
        missing.append("C007_CROSS_OWNER_PAIRING_POLICY_INVALID")
    else:
        missing.append("C007_CROSS_OWNER_PAIRING_POLICY")

    missing = list(dict.fromkeys(missing))
    ready = not missing
    return FormalAcceptanceAuthority(
        frozen_model_policy=model_policy,
        authorized_models=authorized_models,
        actual_requirement=actual_requirement,
        multimodal_required=multimodal_required,
        pairing_policy_reference=pairing_policy,
        pairing_authority_ready=pairing_policy == FROZEN_PAIRING_POLICY,
        pairing_authority_required=pairing_policy != FROZEN_PAIRING_POLICY,
        compatibility_path=compatibility_path,
        status="AUTHORIZED" if ready else "BLOCKED_AUTHORITY_REQUIRED",
        ready=ready,
        missing_fields=tuple(missing),
    )


class FormalExecutionInput(_ReleaseModel):
    """T05-owned result plus public-loader and source identity binding."""

    execution_result: SkipValidation[ExecutionResult]
    source_path: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_run_id: str = Field(min_length=1)
    input_identity: str = Field(min_length=1)
    canonical_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pairing_id: str | None = None
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_loader_reference: str = Field(min_length=1)
    publicly_verified: bool
    checksum_verification: Literal["PASS", "FAIL"]

    @field_validator("execution_result", mode="before")
    @classmethod
    def _require_public_typed_result(cls, value: Any) -> Any:
        if not isinstance(value, ExecutionResult):
            raise ValueError("T05_PUBLIC_LOADER_REQUIRED")
        return value

    @model_validator(mode="after")
    def _validate_source_hash(self) -> "FormalExecutionInput":
        if execution_result_hash(self.execution_result) != self.source_hash:
            raise ValueError("T05_SOURCE_HASH_MISMATCH")
        return self


class FormalMultimodalInput(_ReleaseModel):
    """T06-owned artifact plus case, run, checksum, and provenance binding."""

    artifact: SkipValidation[MultimodalArtifact]
    question_id: str = Field(pattern=r"^Q[0-9]{3}$")
    source_path: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_run_id: str = Field(min_length=1)
    input_identity: str = Field(min_length=1)
    canonical_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pairing_id: str | None = None
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    checksum_verification: Literal["PASS", "FAIL"]
    actual: bool
    mock_mode: bool
    provenance_complete: bool

    @field_validator("artifact", mode="before")
    @classmethod
    def _require_typed_artifact(cls, value: Any) -> Any:
        if not isinstance(value, MultimodalArtifact):
            raise ValueError("T06_TYPED_ARTIFACT_REQUIRED")
        return value

    @model_validator(mode="after")
    def _validate_source_hash(self) -> "FormalMultimodalInput":
        if multimodal_artifact_hash(self.artifact) != self.source_hash:
            raise ValueError("T06_SOURCE_HASH_MISMATCH")
        return self


class FormalReviewerFeedbackBinding(_ReleaseModel):
    """Portable Reviewer identity and target-version lineage binding."""

    question_id: str = Field(pattern=r"^Q[0-9]{3}$")
    source_run_id: str = Field(min_length=1)
    target_version_id: str = Field(min_length=1)
    lineage: tuple[str, ...] = Field(min_length=1)
    feedback_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance_complete: bool

    @model_validator(mode="after")
    def _validate_target_lineage(self) -> "FormalReviewerFeedbackBinding":
        if self.target_version_id not in self.lineage:
            raise ValueError("Reviewer target version is outside the case lineage")
        if len(self.lineage) != len(set(self.lineage)):
            raise ValueError("Reviewer lineage contains duplicate versions")
        return self


class FormalPairingMetadata(_ReleaseModel):
    """Frozen case-table inputs used by the exact FROZEN_V1 machine rule."""

    policy_reference: PairingPolicy
    authority_provenance: str = Field(min_length=1)
    question_id: str = Field(pattern=r"^Q[0-9]{3}$")
    input_identity: str = Field(min_length=1)
    canonical_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pairing_id: str = Field(min_length=1)
    case_run_id: str = Field(min_length=1)
    allow_cross_run_pairing: bool = False
    authorized_source_commits: tuple[str, ...] = ()
    attested_integration_tip: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{40}$",
    )
    reviewer_feedback: FormalReviewerFeedbackBinding

    @field_validator("authorized_source_commits")
    @classmethod
    def _validate_authorized_commits(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("authorized source commits must be unique")
        if any(not re.fullmatch(r"[0-9a-f]{40}", value) for value in values):
            raise ValueError("authorized source commits must be 40-hex Git SHAs")
        return values


class FormalCaseInput(_ReleaseModel):
    """One typed T05+T06 input bundle for one frozen unique C007 run."""

    question_id: str = Field(pattern=r"^Q[0-9]{3}$")
    logical_labels: tuple[str, ...] = Field(min_length=1)
    shared_run: bool
    execution: FormalExecutionInput | None = None
    multimodal: tuple[FormalMultimodalInput, ...] = ()
    input_identity: str = Field(min_length=1)
    canonical_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pairing: FormalPairingMetadata | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_wrong_identity_early(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        labels = tuple(value.get("logical_labels") or ())
        if len(labels) != len(set(labels)):
            raise ValueError("formal case logical labels must be unique")
        question_id = value.get("question_id")
        expected = next(
            (item for item in FORMAL_CASE_SPECS if item[1] == question_id),
            None,
        )
        if expected is not None:
            _, _, expected_labels, expected_shared = expected
            if labels != expected_labels or value.get("shared_run") != expected_shared:
                raise ValueError(
                    "formal case question/logical labels/shared identity mismatch"
                )
        elif question_id:
            raise ValueError("formal case question is not in the frozen case set")
        return value

    @model_validator(mode="after")
    def _validate_case_binding(self) -> "FormalCaseInput":
        if len(self.logical_labels) != len(set(self.logical_labels)):
            raise ValueError("formal case logical labels must be unique")
        expected = next(
            (item for item in FORMAL_CASE_SPECS if item[1] == self.question_id),
            None,
        )
        if expected is None:
            raise ValueError("formal case question is not in the frozen case set")
        _, _, labels, shared = expected
        if self.logical_labels != labels or self.shared_run != shared:
            raise ValueError(
                "formal case question/logical labels/shared identity mismatch"
            )
        if self.execution is not None:
            if self.execution.execution_result.question_id != self.question_id:
                raise ValueError("T05 question identity mismatch")
            if self.execution.input_identity != self.input_identity:
                raise ValueError("T05 input identity mismatch")
            if (
                self.execution.canonical_input_sha256
                != self.canonical_input_sha256
            ):
                raise ValueError("T05 canonical input SHA-256 mismatch")
        artifact_ids: list[str] = []
        for binding in self.multimodal:
            artifact_ids.append(binding.artifact.artifact_id)
            if binding.question_id != self.question_id:
                raise ValueError("T06 question identity mismatch")
            if binding.input_identity != self.input_identity:
                raise ValueError("T06 input identity mismatch")
            if binding.canonical_input_sha256 != self.canonical_input_sha256:
                raise ValueError("T06 canonical input SHA-256 mismatch")
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("T06 artifact IDs must be unique per formal case")
        if self.pairing is not None:
            if self.pairing.question_id != self.question_id:
                raise ValueError("pairing question identity mismatch")
            if self.pairing.input_identity != self.input_identity:
                raise ValueError("pairing input identity mismatch")
            if (
                self.pairing.canonical_input_sha256
                != self.canonical_input_sha256
            ):
                raise ValueError("pairing canonical input SHA-256 mismatch")
        return self


class FormalPairingDecision(_ReleaseModel):
    """Machine-readable FROZEN_V1 record; no heuristic fields are accepted."""

    policy: Literal["C007_CROSS_OWNER_PAIRING_POLICY=FROZEN_V1"]
    question_id: str = Field(pattern=r"^Q[0-9]{3}$")
    canonical_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pairing_id: str = Field(min_length=1)
    t05_run_id: str = Field(min_length=1)
    t06_run_id: str = Field(min_length=1)
    t05_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    t06_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    reviewer_run_id: str = Field(min_length=1)
    reviewer_target_version_id: str = Field(min_length=1)
    cross_run: Literal["SAME_RUN", "DIFFERENT_RUN"]
    cross_commit: Literal["SAME_COMMIT", "DIFFERENT_COMMIT"]
    checksum_verification: Literal["PASS", "FAIL"]
    pairing_result: Literal["PASS", "FAIL"]
    fail_reason: str | None = None

    @model_validator(mode="after")
    def _validate_result(self) -> "FormalPairingDecision":
        if (self.pairing_result == "PASS") != (self.fail_reason is None):
            raise ValueError("pairing result and fail reason are inconsistent")
        if self.pairing_result == "PASS" and self.checksum_verification != "PASS":
            raise ValueError("passing pairing requires verified checksums")
        return self


class FormalCaseEligibility(_ReleaseModel):
    """Fail-closed readiness decision evaluated before any Provider preflight."""

    question_id: str = Field(pattern=r"^Q[0-9]{3}$")
    t05_ready: bool
    t06_ready: bool
    pairing_policy: PairingPolicy
    pairing_authority_ready: bool
    pairing_ready: bool
    pairing_authority_required: bool
    pairing_record: FormalPairingDecision | None = None
    eligible_for_provider_run: bool
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_decision(self) -> "FormalCaseEligibility":
        expected = bool(
            self.t05_ready
            and self.t06_ready
            and self.pairing_ready
            and not self.blockers
        )
        if self.eligible_for_provider_run != expected:
            raise ValueError("formal case eligibility decision is inconsistent")
        if self.pairing_policy != FROZEN_PAIRING_POLICY:
            raise ValueError("formal case pairing policy is not frozen")
        if (
            not self.pairing_authority_ready
            or self.pairing_authority_required
        ):
            raise ValueError("pairing authority readiness is inconsistent")
        if self.pairing_ready != bool(
            self.pairing_record is not None
            and self.pairing_record.pairing_result == "PASS"
        ):
            raise ValueError("pairing input readiness is inconsistent")
        return self


class PublicExecutionResolution(_ReleaseModel):
    execution_result: ExecutionResult | None = None
    eligible_for_c007: bool
    blocker: str | None = None


def resolve_public_execution_result(
    candidate: object,
    *,
    public_loader_reference: str | None = None,
) -> PublicExecutionResolution:
    """Accept only a typed result returned by a named public T05 loader."""

    if not isinstance(candidate, ExecutionResult) or not public_loader_reference:
        return PublicExecutionResolution(
            eligible_for_c007=False,
            blocker="T05_PUBLIC_LOADER_REQUIRED",
        )
    return PublicExecutionResolution(
        execution_result=candidate,
        eligible_for_c007=True,
    )


def _git_commit_is_ancestor(commit: str, tip: str) -> bool:
    """Return a machine-checkable Git ancestry result; errors fail closed."""

    process = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, tip],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return process.returncode == 0


def _evaluate_formal_pairing(
    value: FormalCaseInput,
    *,
    commit_ancestor_verifier: Callable[[str, str], bool] = _git_commit_is_ancestor,
) -> tuple[FormalPairingDecision | None, tuple[str, ...]]:
    """Apply the Captain-owned FROZEN_V1 rule without heuristic inference."""

    execution = value.execution
    pairing = value.pairing
    if execution is None or not value.multimodal:
        return None, ()
    if pairing is None:
        return None, ("PAIRING_METADATA_REQUIRED",)

    blockers: list[str] = []
    result = execution.execution_result
    bindings = tuple(
        sorted(value.multimodal, key=lambda item: item.artifact.artifact_id)
    )
    reviewer = pairing.reviewer_feedback
    t06_runs = tuple(dict.fromkeys(item.source_run_id for item in bindings))
    t06_commits = tuple(dict.fromkeys(item.source_commit for item in bindings))
    t06_run_id = t06_runs[0]
    t06_commit = t06_commits[0]

    if pairing.policy_reference != FROZEN_PAIRING_POLICY:
        blockers.append("PAIRING_POLICY_INVALID")
    if (
        result.question_id != value.question_id
        or any(item.question_id != value.question_id for item in bindings)
        or reviewer.question_id != value.question_id
        or pairing.question_id != value.question_id
    ):
        blockers.append("PAIRING_QUESTION_MISMATCH")
    canonical_hashes = {
        value.canonical_input_sha256,
        execution.canonical_input_sha256,
        pairing.canonical_input_sha256,
        *(item.canonical_input_sha256 for item in bindings),
    }
    if len(canonical_hashes) != 1:
        blockers.append("PAIRING_CANONICAL_INPUT_SHA256_MISMATCH")
    if result.mode != "actual" or not result.actual_execution:
        blockers.append("PAIRING_T05_ACTUAL_EXECUTION_REQUIRED")
    forbidden_source_markers = ("fixture", "synthetic", "planned", "expected")
    if any(
        not item.actual
        or item.mock_mode
        or any(
            marker in item.artifact.provenance.source_type.casefold()
            for marker in forbidden_source_markers
        )
        or item.artifact.validation_status != "passed"
        for item in bindings
    ):
        blockers.append("PAIRING_T06_PRODUCTION_ARTIFACT_REQUIRED")
    if (
        not result.provenance_complete
        or any(not item.provenance_complete for item in bindings)
        or not reviewer.provenance_complete
    ):
        blockers.append("PAIRING_PROVENANCE_INCOMPLETE")
    if (
        not execution.source_run_id
        or any(not item.source_run_id for item in bindings)
        or not reviewer.source_run_id
    ):
        blockers.append("PAIRING_RUN_ID_REQUIRED")
    t05_checksums_pass = bool(
        execution.checksum_verification == "PASS"
        and result.artifacts_validated
        and result.artifacts
        and all(
            item.validation_status == "valid" and item.sha256
            for item in result.artifacts
        )
    )
    t06_checksums_pass = all(
        item.checksum_verification == "PASS" and item.artifact_checksum
        for item in bindings
    )
    checksum_status: Literal["PASS", "FAIL"] = (
        "PASS" if t05_checksums_pass and t06_checksums_pass else "FAIL"
    )
    if checksum_status != "PASS":
        blockers.append("PAIRING_CHECKSUM_VERIFICATION_FAILED")
    if (
        reviewer.source_run_id != pairing.case_run_id
        or reviewer.target_version_id not in reviewer.lineage
    ):
        blockers.append("PAIRING_REVIEWER_LINEAGE_MISMATCH")

    if len(t06_runs) != 1:
        blockers.append("PAIRING_T06_RUN_ID_AMBIGUOUS")
    cross_run: Literal["SAME_RUN", "DIFFERENT_RUN"] = (
        "SAME_RUN"
        if execution.source_run_id == t06_run_id and len(t06_runs) == 1
        else "DIFFERENT_RUN"
    )
    if cross_run == "DIFFERENT_RUN":
        if not pairing.allow_cross_run_pairing:
            blockers.append("PAIRING_CROSS_RUN_NOT_AUTHORIZED")
        if (
            not execution.pairing_id
            or execution.pairing_id != pairing.pairing_id
            or any(item.pairing_id != pairing.pairing_id for item in bindings)
        ):
            blockers.append("PAIRING_ID_MISMATCH")

    if len(t06_commits) != 1:
        blockers.append("PAIRING_T06_SOURCE_COMMIT_AMBIGUOUS")
    cross_commit: Literal["SAME_COMMIT", "DIFFERENT_COMMIT"] = (
        "SAME_COMMIT"
        if execution.source_commit == t06_commit and len(t06_commits) == 1
        else "DIFFERENT_COMMIT"
    )
    if cross_commit == "DIFFERENT_COMMIT":
        authorized = set(pairing.authorized_source_commits)
        allowlisted = {
            execution.source_commit,
            *t06_commits,
        }.issubset(authorized)
        ancestry_attested = bool(
            pairing.attested_integration_tip
            and commit_ancestor_verifier(
                execution.source_commit,
                pairing.attested_integration_tip,
            )
            and all(
                commit_ancestor_verifier(
                    source_commit,
                    pairing.attested_integration_tip,
                )
                for source_commit in t06_commits
            )
        )
        if not (allowlisted or ancestry_attested):
            blockers.append("PAIRING_CROSS_COMMIT_NOT_AUTHORIZED")

    blockers = list(dict.fromkeys(blockers))
    fail_reason = ";".join(blockers) or None
    decision = FormalPairingDecision(
        policy="C007_CROSS_OWNER_PAIRING_POLICY=FROZEN_V1",
        question_id=value.question_id,
        canonical_input_sha256=value.canonical_input_sha256,
        pairing_id=pairing.pairing_id,
        t05_run_id=execution.source_run_id,
        t06_run_id=t06_run_id,
        t05_source_commit=execution.source_commit,
        t06_source_commit=t06_commit,
        reviewer_run_id=reviewer.source_run_id,
        reviewer_target_version_id=reviewer.target_version_id,
        cross_run=cross_run,
        cross_commit=cross_commit,
        checksum_verification=checksum_status,
        pairing_result="FAIL" if blockers else "PASS",
        fail_reason=fail_reason,
    )
    return decision, tuple(blockers)


def assess_formal_case_input(
    value: FormalCaseInput,
    *,
    canonical_input: Mapping[str, Any] | None = None,
    commit_ancestor_verifier: Callable[[str, str], bool] = _git_commit_is_ancestor,
) -> FormalCaseEligibility:
    """Evaluate all T05/T06/pairing gates without calling the pipeline or Provider."""

    t05_blockers: list[str] = []
    t06_blockers: list[str] = []
    pairing_blockers: list[str] = []
    execution = value.execution
    if execution is None:
        t05_blockers.append("T05_INPUT_REQUIRED")
    else:
        result = execution.execution_result
        if not execution.publicly_verified or not execution.public_loader_reference:
            t05_blockers.append("T05_PUBLIC_LOADER_REQUIRED")
        if result.mode != "actual" or not result.actual_execution:
            t05_blockers.append("T05_ACTUAL_EXECUTION_REQUIRED")
        if result.question_id != value.question_id:
            t05_blockers.append("T05_QUESTION_MISMATCH")
        if result.status != "succeeded" or result.error is not None:
            t05_blockers.append("T05_SUCCESS_STATUS_REQUIRED")
        if result.entrypoint_class != "scientific":
            t05_blockers.append("T05_SCIENTIFIC_ENTRYPOINT_REQUIRED")
        required_truth = (
            result.runner_verified,
            result.provenance_complete,
            result.datasets_validated,
            result.artifacts_validated,
            result.metrics_validated,
            result.scientific_result_usable,
        )
        if not all(required_truth):
            t05_blockers.append("T05_PROVENANCE_OR_VALIDATION_INCOMPLETE")
        if (
            not result.process_started
            or not result.process_reaped
            or result.process_alive_after_cleanup
            or result.exit_code != 0
            or not result.artifacts
            or not result.metrics
        ):
            t05_blockers.append("T05_EMPTY_SHELL_OR_PROCESS_INVALID")
        if execution_result_hash(result) != execution.source_hash:
            t05_blockers.append("T05_SOURCE_HASH_MISMATCH")
        if execution.checksum_verification != "PASS":
            t05_blockers.append("T05_CHECKSUM_VERIFICATION_REQUIRED")

    if not value.multimodal:
        t06_blockers.append("T06_INPUT_REQUIRED")
    for binding in value.multimodal:
        artifact = binding.artifact
        if not binding.actual or binding.mock_mode:
            t06_blockers.append("T06_ACTUAL_NON_MOCK_REQUIRED")
        if any(
            marker in artifact.provenance.source_type.casefold()
            for marker in ("fixture", "synthetic", "planned", "expected")
        ):
            t06_blockers.append("T06_FIXTURE_NOT_ALLOWED")
        if binding.question_id != value.question_id:
            t06_blockers.append("T06_QUESTION_MISMATCH")
        if not binding.provenance_complete:
            t06_blockers.append("T06_PROVENANCE_REQUIRED")
        if artifact.validation_status != "passed":
            t06_blockers.append("T06_VALIDATION_PASSED_REQUIRED")
        try:
            summary = to_consumer_summary(artifact)
        except (TypeError, ValueError, ValidationError):
            t06_blockers.append("T06_CONSUMER_SUMMARY_INVALID")
        else:
            if not summary.artifact_id or summary.header_count < 1:
                t06_blockers.append("T06_REQUIRED_FIELDS_INCOMPLETE")
        if multimodal_artifact_hash(artifact) != binding.source_hash:
            t06_blockers.append("T06_SOURCE_HASH_MISMATCH")
        if not binding.artifact_checksum:
            t06_blockers.append("T06_ARTIFACT_CHECKSUM_REQUIRED")
        if binding.checksum_verification != "PASS":
            t06_blockers.append("T06_CHECKSUM_VERIFICATION_REQUIRED")

    if (
        canonical_input is not None
        and canonical_sha256(dict(canonical_input)) != value.canonical_input_sha256
    ):
        pairing_blockers.append("PAIRING_CANONICAL_INPUT_SHA256_MISMATCH")

    pairing_record, machine_pairing_blockers = _evaluate_formal_pairing(
        value,
        commit_ancestor_verifier=commit_ancestor_verifier,
    )
    pairing_blockers.extend(machine_pairing_blockers)
    blockers = tuple(dict.fromkeys((*t05_blockers, *t06_blockers, *pairing_blockers)))
    t05_ready = not t05_blockers
    t06_ready = not t06_blockers
    pairing_ready = bool(
        pairing_record is not None and pairing_record.pairing_result == "PASS"
    )
    return FormalCaseEligibility(
        question_id=value.question_id,
        t05_ready=t05_ready,
        t06_ready=t06_ready,
        pairing_policy=FROZEN_PAIRING_POLICY,
        pairing_authority_ready=True,
        pairing_ready=pairing_ready,
        pairing_authority_required=False,
        pairing_record=pairing_record,
        eligible_for_provider_run=bool(
            t05_ready and t06_ready and pairing_ready and not blockers
        ),
        blockers=blockers,
    )


class FormalInputHashes(_ReleaseModel):
    execution_result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_summary_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    multimodal_artifact_hashes: dict[str, str]
    multimodal_consumer_summary_hashes: dict[str, str]
    multimodal_artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    multimodal_consumer_summary_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class FormalExecutionSourceEvidence(_ReleaseModel):
    source_path: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_run_id: str = Field(min_length=1)
    input_identity: str = Field(min_length=1)
    canonical_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pairing_id: str | None = None
    checksum_verification: Literal["PASS", "FAIL"]
    public_loader_reference: str = Field(min_length=1)


class FormalMultimodalSourceEvidence(_ReleaseModel):
    artifact_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_run_id: str = Field(min_length=1)
    input_identity: str = Field(min_length=1)
    canonical_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pairing_id: str | None = None
    artifact_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    checksum_verification: Literal["PASS", "FAIL"]


class FormalInputsEvidence(FormalInputHashes):
    execution_source: FormalExecutionSourceEvidence
    multimodal_sources: tuple[FormalMultimodalSourceEvidence, ...]


class FormalAuthorityEvidence(_ReleaseModel):
    model_policy: FrozenModelPolicy
    authorized_models: tuple[AuthorizedModel, ...]
    actual_requirement: ActualExecutionRequirement
    multimodal_required: Literal[True] = True
    pairing_policy_reference: PairingPolicy


def compute_formal_input_hashes(value: FormalCaseInput) -> FormalInputHashes:
    if value.execution is None or not value.multimodal:
        raise ValueError("complete typed T05/T06 inputs are required for hashing")
    artifact_hashes = {
        binding.artifact.artifact_id: multimodal_artifact_hash(binding.artifact)
        for binding in sorted(value.multimodal, key=lambda item: item.artifact.artifact_id)
    }
    summary_hashes = {
        binding.artifact.artifact_id: multimodal_consumer_summary_hash(
            binding.artifact
        )
        for binding in sorted(value.multimodal, key=lambda item: item.artifact.artifact_id)
    }
    return FormalInputHashes(
        execution_result_hash=execution_result_hash(
            value.execution.execution_result
        ),
        execution_summary_hash=execution_summary_hash(
            value.execution.execution_result
        ),
        multimodal_artifact_hashes=artifact_hashes,
        multimodal_consumer_summary_hashes=summary_hashes,
        multimodal_artifact_hash=canonical_sha256(
            [{"artifact_id": key, "hash": artifact_hashes[key]} for key in artifact_hashes]
        ),
        multimodal_consumer_summary_hash=canonical_sha256(
            [{"artifact_id": key, "hash": summary_hashes[key]} for key in summary_hashes]
        ),
    )


def build_formal_inputs_evidence(
    value: FormalCaseInput,
    hashes: FormalInputHashes,
) -> FormalInputsEvidence:
    if value.execution is None:
        raise ValueError("formal input evidence requires T05 source binding")
    return FormalInputsEvidence(
        **hashes.model_dump(mode="python"),
        execution_source=FormalExecutionSourceEvidence(
            source_path=_canonical_path_identity(value.execution.source_path),
            source_commit=value.execution.source_commit,
            source_run_id=value.execution.source_run_id,
            input_identity=value.execution.input_identity,
            canonical_input_sha256=value.execution.canonical_input_sha256,
            pairing_id=value.execution.pairing_id,
            checksum_verification=value.execution.checksum_verification,
            public_loader_reference=value.execution.public_loader_reference,
        ),
        multimodal_sources=tuple(
            FormalMultimodalSourceEvidence(
                artifact_id=binding.artifact.artifact_id,
                source_path=_canonical_path_identity(binding.source_path),
                source_commit=binding.source_commit,
                source_run_id=binding.source_run_id,
                input_identity=binding.input_identity,
                canonical_input_sha256=binding.canonical_input_sha256,
                pairing_id=binding.pairing_id,
                artifact_checksum=binding.artifact_checksum,
                checksum_verification=binding.checksum_verification,
            )
            for binding in sorted(
                value.multimodal,
                key=lambda item: item.artifact.artifact_id,
            )
        ),
    )


class FormalRevisionContextBinding(FormalInputHashes):
    revision_context_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision_feedback_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


def build_revision_context_binding(
    formal_input: FormalCaseInput,
    input_hashes: FormalInputHashes,
    context: ExperimentRevisionContext,
) -> FormalRevisionContextBinding:
    feedback = context.wave_c_feedback
    if feedback is None or feedback.execution is None or not feedback.multimodal:
        raise ValueError("formal RevisionContext lacks complete T05/T06 projection")
    if canonical_evidence_sha256(feedback.execution) != input_hashes.execution_summary_hash:
        raise ValueError("RevisionContext execution summary hash mismatch")
    context_multimodal = {
        item.artifact_id: canonical_evidence_sha256(item)
        for item in feedback.multimodal
    }
    if context_multimodal != input_hashes.multimodal_consumer_summary_hashes:
        raise ValueError("RevisionContext multimodal summary hashes mismatch")
    if formal_input.execution is None:
        raise ValueError("formal RevisionContext binding requires T05 input")
    if feedback.execution.execution_id != formal_input.execution.execution_result.execution_id:
        raise ValueError("RevisionContext execution identity mismatch")
    return FormalRevisionContextBinding(
        **input_hashes.model_dump(mode="python"),
        revision_context_fingerprint=canonical_evidence_sha256(context),
        revision_feedback_fingerprint=feedback.fingerprint,
    )


class FormalPromptImpactLink(_ReleaseModel):
    stage: str = Field(min_length=1)
    next_prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class FormalSourceImpact(_ReleaseModel):
    source_kind: Literal["execution", "multimodal"]
    source_id: str = Field(min_length=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision_context_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_links: tuple[FormalPromptImpactLink, ...]
    v2_version_id: str = Field(min_length=1)
    linked_change_ids: tuple[str, ...] = ()
    linked_sections: tuple[str, ...] = ()
    impact_status: Literal["PROVEN", "UNPROVEN"]

    @model_validator(mode="after")
    def _validate_impact_claim(self) -> "FormalSourceImpact":
        proven = bool(
            self.prompt_links and self.linked_change_ids and self.linked_sections
        )
        if self.impact_status != ("PROVEN" if proven else "UNPROVEN"):
            raise ValueError("formal source impact claim is inconsistent")
        return self


class FormalImpactTrace(_ReleaseModel):
    execution_impact: FormalSourceImpact
    multimodal_impact: tuple[FormalSourceImpact, ...]

    @property
    def all_proven(self) -> bool:
        return bool(
            self.execution_impact.impact_status == "PROVEN"
            and self.multimodal_impact
            and all(item.impact_status == "PROVEN" for item in self.multimodal_impact)
        )


def _change_mentions(change: Any, markers: Sequence[str]) -> bool:
    payload = json.dumps(
        {
            "reason": change.reason,
            "after": change.after,
            "evidence_refs": change.evidence_refs,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).casefold()
    return any(marker.casefold() in payload for marker in markers if marker)


def build_formal_impact_trace(
    *,
    formal_input: FormalCaseInput,
    input_hashes: FormalInputHashes,
    context_binding: FormalRevisionContextBinding,
    next_prompt_hashes: Mapping[str, str],
    v2_version_id: str,
    structured_diff: StructuredRevisionDiff,
) -> FormalImpactTrace:
    """Deterministically link source identities to prompt provenance and V2 changes."""

    if formal_input.execution is None:
        raise ValueError("execution input is required for impact tracing")
    prompt_links = tuple(
        FormalPromptImpactLink(stage=stage, next_prompt_hash=prompt_hash)
        for stage, prompt_hash in sorted(next_prompt_hashes.items())
    )
    execution_result = formal_input.execution.execution_result
    execution_markers = (
        execution_result.execution_id,
        *(item.artifact_id for item in execution_result.artifacts),
        *(item.name for item in execution_result.metrics),
    )
    execution_changes = tuple(
        change
        for change in structured_diff.changes
        if _change_mentions(change, execution_markers)
    )
    execution_impact = FormalSourceImpact(
        source_kind="execution",
        source_id=execution_result.execution_id,
        source_hash=input_hashes.execution_result_hash,
        summary_hash=input_hashes.execution_summary_hash,
        revision_context_fingerprint=(
            context_binding.revision_context_fingerprint
        ),
        prompt_links=prompt_links,
        v2_version_id=v2_version_id,
        linked_change_ids=tuple(change.change_id for change in execution_changes),
        linked_sections=tuple(
            dict.fromkeys(change.affected_plan_section for change in execution_changes)
        ),
        impact_status=("PROVEN" if prompt_links and execution_changes else "UNPROVEN"),
    )
    multimodal_impacts: list[FormalSourceImpact] = []
    for binding in sorted(
        formal_input.multimodal,
        key=lambda item: item.artifact.artifact_id,
    ):
        artifact_id = binding.artifact.artifact_id
        changes = tuple(
            change
            for change in structured_diff.changes
            if _change_mentions(change, (artifact_id,))
        )
        multimodal_impacts.append(
            FormalSourceImpact(
                source_kind="multimodal",
                source_id=artifact_id,
                source_hash=input_hashes.multimodal_artifact_hashes[artifact_id],
                summary_hash=(
                    input_hashes.multimodal_consumer_summary_hashes[artifact_id]
                ),
                revision_context_fingerprint=(
                    context_binding.revision_context_fingerprint
                ),
                prompt_links=prompt_links,
                v2_version_id=v2_version_id,
                linked_change_ids=tuple(change.change_id for change in changes),
                linked_sections=tuple(
                    dict.fromkeys(change.affected_plan_section for change in changes)
                ),
                impact_status=("PROVEN" if prompt_links and changes else "UNPROVEN"),
            )
        )
    return FormalImpactTrace(
        execution_impact=execution_impact,
        multimodal_impact=tuple(multimodal_impacts),
    )


class FormalModelCallLedgerEntry(_ReleaseModel):
    call_id: str
    agent_name: str
    stage: str
    round: int | None = Field(default=None, ge=1)
    model: str
    provider: str
    status: str
    started_at: str | None = None
    ended_at: str | None = None


class FormalModelRouteAudit(_ReleaseModel):
    authorized_models: tuple[str, ...]
    total_model_calls: int = Field(ge=0)
    per_model_call_counts: dict[str, int]
    stage_model_mapping: dict[str, tuple[str, ...]]
    round_model_mapping: dict[str, tuple[str, ...]]
    unauthorized_model_calls: int = Field(ge=0)
    unauthorized_call_ids: tuple[str, ...] = ()
    ledger_complete: bool
    call_ledger: tuple[FormalModelCallLedgerEntry, ...]
    qualified: bool

    @model_validator(mode="after")
    def _validate_route(self) -> "FormalModelRouteAudit":
        if sum(self.per_model_call_counts.values()) != self.total_model_calls:
            raise ValueError("model route counts do not match total calls")
        expected = bool(
            self.total_model_calls > 0
            and self.unauthorized_model_calls == 0
            and self.ledger_complete
        )
        if self.qualified != expected:
            raise ValueError("model route qualification is inconsistent")
        return self


def build_model_route_audit(
    calls: Sequence[Mapping[str, Any]],
    *,
    authorized_models: Sequence[str],
) -> FormalModelRouteAudit:
    """Materialize the full real-call ledger, including mixed and failed calls."""

    authorized = tuple(authorized_models)
    allowed = frozenset(authorized)
    counts: dict[str, int] = {}
    stage_models: dict[str, list[str]] = {}
    round_models: dict[str, list[str]] = {}
    occurrences: dict[str, int] = {}
    unauthorized_ids: list[str] = []
    ledger: list[FormalModelCallLedgerEntry] = []
    ledger_complete = True
    for index, call in enumerate(calls, start=1):
        if call.get("mock") or call.get("provider") == "mock":
            continue
        call_id = str(call.get("call_id") or "").strip()
        stage = str(call.get("agent_name") or "").strip()
        model = str(
            call.get("model") or call.get("model_name_internal") or ""
        ).strip()
        provider = str(call.get("provider") or "").strip()
        status = str(call.get("status") or "").strip()
        if not all((call_id, stage, model, provider, status)):
            ledger_complete = False
        effective_call_id = call_id or f"missing-call-id-{index}"
        effective_stage = stage or "missing-stage"
        effective_model = model or "missing-model"
        effective_provider = provider or "missing-provider"
        effective_status = status or "missing-status"
        occurrences[effective_stage] = occurrences.get(effective_stage, 0) + 1
        round_index = occurrences[effective_stage]
        counts[effective_model] = counts.get(effective_model, 0) + 1
        stage_models.setdefault(effective_stage, []).append(effective_model)
        round_models.setdefault(
            f"{effective_stage}:round_{round_index}", []
        ).append(effective_model)
        if effective_model not in allowed:
            unauthorized_ids.append(effective_call_id)
        ledger.append(
            FormalModelCallLedgerEntry(
                call_id=effective_call_id,
                agent_name=effective_stage,
                stage=effective_stage,
                round=round_index,
                model=effective_model,
                provider=effective_provider,
                status=effective_status,
                started_at=(str(call.get("started_at")) if call.get("started_at") else None),
                ended_at=(str(call.get("ended_at")) if call.get("ended_at") else None),
            )
        )
    normalized_counts = {key: counts[key] for key in sorted(counts)}
    normalized_stages = {
        key: tuple(dict.fromkeys(stage_models[key])) for key in sorted(stage_models)
    }
    normalized_rounds = {
        key: tuple(dict.fromkeys(round_models[key])) for key in sorted(round_models)
    }
    total = len(ledger)
    unauthorized_count = len(unauthorized_ids)
    return FormalModelRouteAudit(
        authorized_models=authorized,
        total_model_calls=total,
        per_model_call_counts=normalized_counts,
        stage_model_mapping=normalized_stages,
        round_model_mapping=normalized_rounds,
        unauthorized_model_calls=unauthorized_count,
        unauthorized_call_ids=tuple(unauthorized_ids),
        ledger_complete=ledger_complete,
        call_ledger=tuple(ledger),
        qualified=bool(total > 0 and unauthorized_count == 0 and ledger_complete),
    )


def summarize_actual_model_calls(
    calls: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, ...], dict[str, int]]:
    """Preserve every real model identity and its exact observed call count."""

    counts: dict[str, int] = {}
    for call in calls:
        identity = str(call.get("model") or call.get("model_name_internal") or "").strip()
        if not identity:
            raise ValueError("real provider call is missing model identity")
        counts[identity] = counts.get(identity, 0) + 1
    identities = tuple(sorted(counts))
    return identities, {identity: counts[identity] for identity in identities}


def validation_status_qualified(status: str | None) -> bool:
    """Only the explicit validated state satisfies formal validation."""

    return status == "validated"


def model_policy_qualified(
    policy: FrozenModelPolicy,
    model_identities: Sequence[str],
) -> bool:
    """Evaluate observed model identities against the Captain-selected policy."""

    observed = frozenset(model_identities)
    if policy != "TIERED_ROUTE_ALLOWED":
        return False
    return bool(observed) and observed.issubset(_AUTHORIZED_MODEL_SET)


def actual_execution_requirement_qualified(
    requirement: ActualExecutionRequirement,
    *,
    actual_execution: bool,
    multimodal_evidence_present: bool,
    real_provider_call_count: int,
) -> bool:
    """Evaluate only the explicitly selected actual-execution requirement."""

    return bool(
        requirement == "T05_EXECUTION_RESULT_REQUIRED"
        and actual_execution
        and multimodal_evidence_present
        and real_provider_call_count >= 1
    )


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
    model_identities: tuple[str, ...] = ()
    model_call_counts: dict[str, int] = Field(default_factory=dict)
    frozen_model_policy: FrozenModelPolicy | None = None
    model_policy_qualified: bool | None = None
    actual_execution_requirement: ActualExecutionRequirement | None = None
    actual_execution: bool | None = None
    actual_execution_qualified: bool | None = None
    multimodal_evidence_present: bool | None = None
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
    authority: FormalAuthorityEvidence | None = None
    inputs: FormalInputsEvidence | None = None
    context_binding: FormalRevisionContextBinding | None = None
    model_route: FormalModelRouteAudit | None = None
    impact: FormalImpactTrace | None = None
    eligibility: FormalCaseEligibility | None = None
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
        if tuple(sorted(self.model_call_counts)) != self.model_identities:
            raise ValueError("formal run model identities do not match call counts")
        if sum(self.model_call_counts.values()) != self.llm_call_count:
            raise ValueError("formal run model call counts do not match call total")
        if self.model_identities:
            expected_model = (
                self.model_identities[0]
                if len(self.model_identities) == 1
                else "mixed"
            )
            if self.model != expected_model or not self.provider:
                raise ValueError("formal run provider/model identity is incomplete")
        if self.status != "SUCCEEDED":
            if self.failure is None or self.result != "FAIL":
                raise ValueError("blocked/failed formal run requires failure evidence")
            return self
        if not self.actual_run_id or not self.provider or not self.model:
            raise ValueError("successful formal run requires real run/provider/model identity")
        if self.llm_call_count < 1 or not self.artifact_checksums:
            raise ValueError("successful formal run requires real calls and artifacts")
        if (
            self.frozen_model_policy is None
            or self.actual_execution_requirement is None
            or self.actual_execution is None
            or self.multimodal_evidence_present is None
        ):
            raise ValueError("successful formal run requires explicit acceptance authority")
        if (
            self.authority is None
            or self.inputs is None
            or self.context_binding is None
            or self.model_route is None
            or self.impact is None
            or self.eligibility is None
            or not self.eligibility.eligible_for_provider_run
        ):
            raise ValueError("successful formal run requires complete readiness evidence")
        if self.authority.model_policy != self.frozen_model_policy:
            raise ValueError("formal authority model policy binding mismatch")
        if self.authority.actual_requirement != self.actual_execution_requirement:
            raise ValueError("formal authority actual requirement binding mismatch")
        if self.model_route.total_model_calls != self.llm_call_count:
            raise ValueError("formal model route total does not match call count")
        if self.model_route.per_model_call_counts != self.model_call_counts:
            raise ValueError("formal model route counts do not match legacy summary")
        if self.context_binding.revision_context_fingerprint != (
            self.revision_context_fingerprint
        ):
            raise ValueError("formal context binding fingerprint mismatch")
        expected_model_qualified = model_policy_qualified(
            self.frozen_model_policy,
            self.model_identities,
        )
        expected_execution_qualified = actual_execution_requirement_qualified(
            self.actual_execution_requirement,
            actual_execution=self.actual_execution,
            multimodal_evidence_present=self.multimodal_evidence_present,
            real_provider_call_count=self.llm_call_count,
        )
        if (
            self.model_policy_qualified != expected_model_qualified
            or self.actual_execution_qualified != expected_execution_qualified
        ):
            raise ValueError("formal run acceptance qualification is inconsistent")
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
            and validation_status_qualified(self.validation_status)
            and self.model_policy_qualified is True
            and self.actual_execution_qualified is True
            and self.model_route.qualified
            and self.impact.all_proven
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
    status: Literal["PASS", "FAIL", "BLOCKED", "BLOCKED_AUTHORITY_REQUIRED"]

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
            else "BLOCKED_AUTHORITY_REQUIRED"
            if any(
                record.failure is not None
                and record.failure.error_type == "AuthorityRequired"
                for record in self.records
            )
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
    """Read and validate the Captain confirmations directly from GitHub."""

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

    pairing_process = subprocess.run(
        [
            "gh",
            "api",
            (
                "repos/sage125-ai-scientist-team/SAGE125-AI-Scientist/"
                f"issues/comments/{PAIRING_AUTHORITY_COMMENT_ID}"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    pairing_payload = json.loads(pairing_process.stdout)
    pairing_body = str(pairing_payload.get("body") or "")
    pairing_required = (
        "AUTHORIZED_BY_CAPTAIN=YES",
        f"CAPTAIN_ACCOUNT={CAPTAIN_LOGIN}",
        "PR=#37",
        f"BOUND_HEAD={PAIRING_AUTHORITY_BOUND_HEAD}",
        "C007_ACTUAL_REQUIREMENT=T05_EXECUTION_RESULT_REQUIRED",
        "T06_MULTIMODAL_EVIDENCE_REQUIRED=YES",
        "C007_CROSS_OWNER_PAIRING_POLICY=FROZEN_V1",
    )
    if pairing_payload.get("user", {}).get("login") != CAPTAIN_LOGIN:
        raise ValueError("pairing authority publisher does not match liuyanbo12")
    pairing_missing = [
        token for token in pairing_required if token not in pairing_body
    ]
    if pairing_missing:
        raise ValueError(
            "pairing authority is missing frozen fields: "
            f"{pairing_missing}"
        )
    if pairing_payload.get("html_url") != PAIRING_AUTHORITY_URL:
        raise ValueError("pairing authority URL does not match frozen authority URL")

    def scalar_field(text: str, name: str) -> str | None:
        match = re.search(
            rf"(?m)^\s*{re.escape(name)}\s*=\s*([^\r\n]+)\s*$",
            text,
        )
        return match.group(1).strip() if match else None

    models_match = re.search(
        r"(?ms)^\s*AUTHORIZED_MODELS\s*=\s*\[(.*?)\]",
        body,
    )
    authorized_models = (
        [
            item.strip()
            for item in models_match.group(1).split(",")
            if item.strip()
        ]
        if models_match
        else None
    )
    exact_fields = {
        "FROZEN_MODEL_POLICY": scalar_field(body, "FROZEN_MODEL_POLICY"),
        "AUTHORIZED_MODELS": authorized_models,
        "C007_ACTUAL_REQUIREMENT": scalar_field(
            pairing_body,
            "C007_ACTUAL_REQUIREMENT",
        ),
        "T06_MULTIMODAL_EVIDENCE_REQUIRED": scalar_field(
            pairing_body,
            "T06_MULTIMODAL_EVIDENCE_REQUIRED"
        ),
        "C007_CROSS_OWNER_PAIRING_POLICY": scalar_field(
            pairing_body,
            "C007_CROSS_OWNER_PAIRING_POLICY",
        ),
    }
    acceptance = resolve_formal_acceptance_authority(exact_fields)
    if not acceptance.ready:
        raise ValueError(
            "Captain confirmation is missing/invalid exact acceptance fields: "
            f"{list(acceptance.missing_fields)}"
        )
    return {
        "url": CAPTAIN_AUTHORITY_URL,
        "original_authority_url": CAPTAIN_ORIGINAL_AUTHORITY_URL,
        "pairing_authority_url": PAIRING_AUTHORITY_URL,
        "login": CAPTAIN_LOGIN,
        "timestamp": payload["created_at"],
        "verified": True,
        "verified_fields": [*required, *pairing_required],
        **exact_fields,
        "frozen_model_policy": acceptance.frozen_model_policy,
        "authorized_models": list(acceptance.authorized_models),
        "actual_requirement": acceptance.actual_requirement,
        "multimodal_required": acceptance.multimodal_required,
        "pairing_authority_ready": acceptance.pairing_authority_ready,
        "pairing_authority_required": acceptance.pairing_authority_required,
        "pairing_policy": acceptance.pairing_policy_reference,
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
    frozen_model_policy: FrozenModelPolicy,
    actual_execution_requirement: ActualExecutionRequirement,
    formal_input: FormalCaseInput,
) -> FormalActualRunRecord:
    """Execute one real pipeline case and derive all evidence from its trace."""

    case_key, question_id, labels, shared = case_spec
    eligibility = assess_formal_case_input(
        formal_input,
        canonical_input=canonical_input,
    )
    if formal_input.question_id != question_id:
        eligibility = FormalCaseEligibility(
            question_id=question_id,
            t05_ready=False,
            t06_ready=False,
            pairing_policy=FROZEN_PAIRING_POLICY,
            pairing_authority_ready=True,
            pairing_ready=False,
            pairing_authority_required=False,
            eligible_for_provider_run=False,
            blockers=("FORMAL_CASE_INPUT_QUESTION_MISMATCH",),
        )
    if not eligibility.eligible_for_provider_run:
        timestamp = datetime.now(timezone.utc)
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
            frozen_model_policy=frozen_model_policy,
            actual_execution_requirement=actual_execution_requirement,
            actual_execution=False,
            actual_execution_qualified=False,
            multimodal_evidence_present=bool(formal_input.multimodal),
            started_at=timestamp,
            ended_at=timestamp,
            execution_status="blocked",
            eligibility=eligibility,
            failure=FormalRunFailure(
                stage="formal_input_eligibility",
                error_type="FormalCaseInputBlocked",
                message="formal T05/T06/pairing eligibility failed before Provider",
                state={
                    "question_id": question_id,
                    "blockers": list(eligibility.blockers),
                    "provider_calls": 0,
                    "pipeline_real_calls": 0,
                },
            ),
            result="FAIL",
        )

    from app.core.config import get_settings
    from app.workflow.artifacts import resolve_artifact_base
    from app.workflow.pipeline import run_pipeline_with_state

    started = datetime.now(timezone.utc)
    run_id: str | None = None
    provider: str | None = None
    model: str | None = None
    model_identities: tuple[str, ...] = ()
    model_call_counts: dict[str, int] = {}
    real_calls: list[dict[str, Any]] = []
    assert formal_input.execution is not None
    assert formal_input.pairing is not None
    input_hashes = compute_formal_input_hashes(formal_input)
    inputs_evidence = build_formal_inputs_evidence(formal_input, input_hashes)
    authority_evidence = FormalAuthorityEvidence(
        model_policy=frozen_model_policy,
        authorized_models=AUTHORIZED_MODEL_IDENTITIES,
        actual_requirement=actual_execution_requirement,
        multimodal_required=True,
        pairing_policy_reference=formal_input.pairing.policy_reference,
    )
    model_route: FormalModelRouteAudit | None = None
    context_binding: FormalRevisionContextBinding | None = None
    impact_trace: FormalImpactTrace | None = None
    actual_execution = formal_input.execution.execution_result.actual_execution
    model_qualified = False
    actual_execution_qualified = False
    multimodal_evidence_present = bool(formal_input.multimodal)
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
                execution_result=formal_input.execution.execution_result,
                multimodal_artifacts=tuple(
                    binding.artifact for binding in formal_input.multimodal
                ),
            )
        ended = datetime.now(timezone.utc)
        run_id = state.run_id
        calls = [_call_dict(item) for item in state.llm_calls]
        real_calls = [
            item
            for item in calls
            if not item.get("mock") and item.get("provider") != "mock"
        ]
        if state.mock_mode or state.run_mode != "real" or not real_calls:
            raise ValueError("formal actual run lacks non-mock provider call evidence")
        provider_identities = tuple(
            sorted({str(item.get("provider") or "").strip() for item in real_calls})
        )
        if not provider_identities or not all(provider_identities):
            raise ValueError("real provider call is missing provider identity")
        provider = (
            provider_identities[0] if len(provider_identities) == 1 else "mixed"
        )
        model_route = build_model_route_audit(
            real_calls,
            authorized_models=AUTHORIZED_MODEL_IDENTITIES,
        )
        model_call_counts = dict(model_route.per_model_call_counts)
        model_identities = tuple(sorted(model_call_counts))
        model = model_identities[0] if len(model_identities) == 1 else "mixed"
        model_qualified = bool(
            model_route.qualified
            and model_policy_qualified(frozen_model_policy, model_identities)
        )
        actual_execution_qualified = actual_execution_requirement_qualified(
            actual_execution_requirement,
            actual_execution=actual_execution,
            multimodal_evidence_present=multimodal_evidence_present,
            real_provider_call_count=len(real_calls),
        )
        run_dir = resolve_artifact_base(get_settings().export_dir) / run_id
        artifact_paths, artifact_checksums = _artifact_inventory(run_dir)
        revision_trace = next(
            (item for item in state.agent_trace if item.get("revision_audit")),
            None,
        )
        if revision_trace is None:
            raise ValueError("formal C007 run did not enter a Reviewer-driven V2")
        store, record, context = _consumer_from_trace(run_id, revision_trace)
        multimodal_evidence_present = bool(
            context.wave_c_feedback is not None
            and context.wave_c_feedback.multimodal
        )
        actual_execution_qualified = actual_execution_requirement_qualified(
            actual_execution_requirement,
            actual_execution=actual_execution,
            multimodal_evidence_present=multimodal_evidence_present,
            real_provider_call_count=len(real_calls),
        )
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
        next_prompt_hashes = dict(second.prompt_fingerprints)
        context_binding = build_revision_context_binding(
            formal_input,
            input_hashes,
            context,
        )
        impact_trace = build_formal_impact_trace(
            formal_input=formal_input,
            input_hashes=input_hashes,
            context_binding=context_binding,
            next_prompt_hashes=next_prompt_hashes,
            v2_version_id=second.version_id,
            structured_diff=diff.diff,
        )
        audit = record.revision_audit
        assert audit is not None
        validation_ok = bool(
            audit.accepted
            and v1_hash != v2_hash
            and p0 == 0
            and p1 == 0
            and artifact_checksums
            and validation_status_qualified(str(plan.validation_status))
            and model_qualified
            and actual_execution_qualified
            and impact_trace.all_proven
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
                    "validation_status_qualified": validation_status_qualified(
                        str(plan.validation_status)
                    ),
                    "model_policy_qualified": model_qualified,
                    "actual_execution_qualified": actual_execution_qualified,
                    "execution_impact_status": (
                        impact_trace.execution_impact.impact_status
                    ),
                    "multimodal_impact_statuses": [
                        item.impact_status for item in impact_trace.multimodal_impact
                    ],
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
            model_identities=model_identities,
            model_call_counts=model_call_counts,
            frozen_model_policy=frozen_model_policy,
            model_policy_qualified=model_qualified,
            actual_execution_requirement=actual_execution_requirement,
            actual_execution=actual_execution,
            actual_execution_qualified=actual_execution_qualified,
            multimodal_evidence_present=multimodal_evidence_present,
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
            revision_context_fingerprint=(
                context_binding.revision_context_fingerprint
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
            authority=authority_evidence,
            inputs=inputs_evidence,
            context_binding=context_binding,
            model_route=model_route,
            impact=impact_trace,
            eligibility=eligibility,
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
            provider=provider,
            model=model,
            model_identities=model_identities,
            model_call_counts=model_call_counts,
            frozen_model_policy=frozen_model_policy,
            model_policy_qualified=model_qualified,
            actual_execution_requirement=actual_execution_requirement,
            actual_execution=actual_execution,
            actual_execution_qualified=actual_execution_qualified,
            multimodal_evidence_present=multimodal_evidence_present,
            started_at=started,
            ended_at=ended,
            llm_call_count=len(real_calls),
            execution_status="failed",
            artifact_paths=artifact_paths,
            artifact_checksums=artifact_checksums,
            authority=authority_evidence,
            inputs=inputs_evidence,
            context_binding=context_binding,
            model_route=model_route,
            impact=impact_trace,
            eligibility=eligibility,
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
    authority: FormalAcceptanceAuthority,
    formal_input: FormalCaseInput,
) -> FormalActualRunRecord:
    case_key, question_id, labels, shared = case_spec
    now = datetime.now(timezone.utc)
    eligibility = assess_formal_case_input(
        formal_input,
        canonical_input=canonical_input,
    )
    input_hashes = compute_formal_input_hashes(formal_input)
    inputs_evidence = build_formal_inputs_evidence(formal_input, input_hashes)
    assert authority.frozen_model_policy is not None
    assert authority.actual_requirement is not None
    assert formal_input.execution is not None
    assert formal_input.pairing is not None
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
        frozen_model_policy=authority.frozen_model_policy,
        actual_execution_requirement=authority.actual_requirement,
        actual_execution=formal_input.execution.execution_result.actual_execution,
        actual_execution_qualified=False,
        multimodal_evidence_present=bool(formal_input.multimodal),
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
        authority=FormalAuthorityEvidence(
            model_policy=authority.frozen_model_policy,
            authorized_models=authority.authorized_models,
            actual_requirement=authority.actual_requirement,
            multimodal_required=True,
            pairing_policy_reference=formal_input.pairing.policy_reference,
        ),
        inputs=inputs_evidence,
        eligibility=eligibility,
        result="FAIL",
    )


def _missing_formal_case_eligibility(question_id: str) -> FormalCaseEligibility:
    return FormalCaseEligibility(
        question_id=question_id,
        t05_ready=False,
        t06_ready=False,
        pairing_policy=FROZEN_PAIRING_POLICY,
        pairing_authority_ready=True,
        pairing_ready=False,
        pairing_authority_required=False,
        eligible_for_provider_run=False,
        blockers=(
            "FORMAL_CASE_INPUT_REQUIRED",
            "T05_INPUT_REQUIRED",
            "T06_INPUT_REQUIRED",
        ),
    )


def _formal_input_blocked_record(
    *,
    case_spec: tuple[str, str, tuple[str, ...], bool],
    canonical_input: dict[str, Any],
    git_sha: str,
    config: dict[str, Any],
    authority: FormalAcceptanceAuthority,
    eligibility: FormalCaseEligibility,
    preflight_path: Path,
) -> FormalActualRunRecord:
    """Materialize a per-case fail-closed decision without importing the pipeline."""

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
        frozen_model_policy=authority.frozen_model_policy,
        actual_execution_requirement=authority.actual_requirement,
        actual_execution=False,
        actual_execution_qualified=False,
        multimodal_evidence_present=False,
        started_at=now,
        ended_at=now,
        execution_status="blocked_before_provider_preflight",
        artifact_paths=(preflight_path.as_posix(),),
        artifact_checksums={preflight_path.as_posix(): _sha256_path(preflight_path)},
        eligibility=eligibility,
        failure=FormalRunFailure(
            stage="formal_input_eligibility",
            error_type="FormalCaseInputBlocked",
            message="; ".join(eligibility.blockers),
            state={
                "question_id": question_id,
                "blockers": list(eligibility.blockers),
                "provider_calls": 0,
                "pipeline_real_calls": 0,
            },
            artifact_paths=(preflight_path.as_posix(),),
        ),
        result="FAIL",
    )


def _authority_blocked_record(
    *,
    case_spec: tuple[str, str, tuple[str, ...], bool],
    canonical_input: dict[str, Any],
    git_sha: str,
    config: dict[str, Any],
    authority: FormalAcceptanceAuthority,
    preflight_path: Path,
) -> FormalActualRunRecord:
    """Emit explicit fail-closed evidence before any provider preflight or call."""

    case_key, question_id, labels, shared = case_spec
    now = datetime.now(timezone.utc)
    missing = ", ".join(authority.missing_fields)
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
        frozen_model_policy=authority.frozen_model_policy,
        actual_execution_requirement=authority.actual_requirement,
        started_at=now,
        ended_at=now,
        execution_status="blocked_before_provider_preflight",
        artifact_paths=(preflight_path.as_posix(),),
        artifact_checksums={preflight_path.as_posix(): _sha256_path(preflight_path)},
        failure=FormalRunFailure(
            stage="formal_acceptance_authority",
            error_type="AuthorityRequired",
            message=f"Captain authority is required for: {missing}",
            state=authority.model_dump(mode="json"),
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


def _assess_formal_input_set(
    values: Sequence[FormalCaseInput],
    *,
    canonical_inputs: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[
    dict[str, FormalCaseInput],
    dict[str, FormalCaseEligibility],
    bool,
]:
    """Require one eligible typed bundle for every frozen unique case."""

    inputs: dict[str, FormalCaseInput] = {}
    duplicate_ids: set[str] = set()
    for value in values:
        if value.question_id in inputs:
            duplicate_ids.add(value.question_id)
        else:
            inputs[value.question_id] = value

    expected_ids = tuple(spec[1] for spec in FORMAL_CASE_SPECS)
    missing_ids = {question_id for question_id in expected_ids if question_id not in inputs}
    unexpected_ids = set(inputs).difference(expected_ids)
    base = {
        question_id: (
            assess_formal_case_input(
                inputs[question_id],
                canonical_input=(
                    canonical_inputs.get(question_id)
                    if canonical_inputs is not None
                    else None
                ),
            )
            if question_id in inputs
            else _missing_formal_case_eligibility(question_id)
        )
        for question_id in expected_ids
    }
    set_incomplete = bool(missing_ids or duplicate_ids or unexpected_ids)
    any_case_blocked = any(
        not item.eligible_for_provider_run for item in base.values()
    )
    eligibility: dict[str, FormalCaseEligibility] = {}
    for question_id, item in base.items():
        extra: list[str] = []
        if question_id in duplicate_ids:
            extra.append("FORMAL_CASE_INPUT_DUPLICATE")
        if set_incomplete or any_case_blocked:
            extra.append("FORMAL_INPUT_SET_INCOMPLETE")
        blockers = tuple(dict.fromkeys((*item.blockers, *extra)))
        eligibility[question_id] = FormalCaseEligibility(
            question_id=question_id,
            t05_ready=item.t05_ready,
            t06_ready=item.t06_ready,
            pairing_policy=item.pairing_policy,
            pairing_authority_ready=item.pairing_authority_ready,
            pairing_ready=item.pairing_ready,
            pairing_authority_required=item.pairing_authority_required,
            pairing_record=item.pairing_record,
            eligible_for_provider_run=bool(
                item.t05_ready
                and item.t06_ready
                and item.pairing_ready
                and not blockers
            ),
            blockers=blockers,
        )
    ready = bool(
        len(values) == len(expected_ids)
        and not unexpected_ids
        and not duplicate_ids
        and all(item.eligible_for_provider_run for item in eligibility.values())
    )
    return inputs, eligibility, ready


def build_formal_readiness_status(
    authority: FormalAcceptanceAuthority,
    eligibility: Mapping[str, FormalCaseEligibility],
) -> dict[str, str]:
    """Expose authority readiness separately from per-case input readiness."""

    values = tuple(eligibility.values())
    all_t05_ready = bool(values) and all(item.t05_ready for item in values)
    all_t06_ready = bool(values) and all(item.t06_ready for item in values)
    all_pairings_ready = bool(values) and all(
        item.pairing_ready for item in values
    )
    all_cases_ready = bool(values) and all(
        item.eligible_for_provider_run for item in values
    )
    return {
        "PAIRING_AUTHORITY_READY": (
            "YES" if authority.pairing_authority_ready else "NO"
        ),
        "PAIRING_AUTHORITY_REQUIRED": (
            "YES" if authority.pairing_authority_required else "NO"
        ),
        "PAIRING_POLICY": authority.pairing_policy_reference or "UNRESOLVED",
        "ALL_T05_READY": "YES" if all_t05_ready else "NO",
        "ALL_T06_READY": "YES" if all_t06_ready else "NO",
        "ALL_PAIRINGS_READY": "YES" if all_pairings_ready else "NO",
        "ALL_CASES_READY_FOR_RERUN": "YES" if all_cases_ready else "NO",
    }


def run_formal_release(
    source_pdf: Path,
    output_dir: Path,
    *,
    formal_case_inputs: Sequence[FormalCaseInput] = (),
) -> dict[str, Any]:
    """Run selection, preflight, four unique real runs, and evidence aggregation."""

    from app.workflow.preflight import run_real_preflight

    authority = verify_captain_authority()
    acceptance_authority = resolve_formal_acceptance_authority(authority)
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
        "formal_acceptance_authority": acceptance_authority.model_dump(mode="json"),
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
    input_by_question, input_eligibility, formal_inputs_ready = (
        _assess_formal_input_set(
            formal_case_inputs,
            canonical_inputs=by_id,
        )
    )
    readiness_status = build_formal_readiness_status(
        acceptance_authority,
        input_eligibility,
    )
    preflight_path = output_dir / "provider_preflight.json"
    if acceptance_authority.ready and formal_inputs_ready:
        preflight = dict(
            _masked(
                run_real_preflight(
                    use_local_rag=False,
                    use_deep_research=False,
                    check_connectivity=True,
                )
            )
        )
        preflight.update(readiness_status)
    elif not acceptance_authority.ready:
        preflight = {
            **readiness_status,
            "ok": False,
            "status": "BLOCKED_AUTHORITY_REQUIRED",
            "authority_blocked": True,
            "errors": [
                "Captain authority is required for: "
                + ", ".join(acceptance_authority.missing_fields)
            ],
            "warnings": [],
            "fix_commands": [],
            "can_run_real": False,
            "can_run_mock": False,
            "connectivity": {"checked": False, "ok": None},
            "formal_acceptance_authority": acceptance_authority.model_dump(
                mode="json"
            ),
        }
    else:
        blocker_rows = [
            f"{question_id}: {', '.join(item.blockers)}"
            for question_id, item in input_eligibility.items()
            if not item.eligible_for_provider_run
        ]
        preflight = {
            **readiness_status,
            "ok": False,
            "status": "BLOCKED_FORMAL_INPUTS",
            "authority_blocked": False,
            "formal_inputs_blocked": True,
            "errors": blocker_rows,
            "warnings": [],
            "fix_commands": [],
            "can_run_real": False,
            "can_run_mock": False,
            "connectivity": {"checked": False, "ok": None},
            "provider_calls": 0,
            "pipeline_real_calls": 0,
            "formal_input_eligibility": {
                question_id: item.model_dump(mode="json")
                for question_id, item in input_eligibility.items()
            },
            "formal_acceptance_authority": acceptance_authority.model_dump(
                mode="json"
            ),
        }
    _write_json(preflight_path, preflight)
    records: list[FormalActualRunRecord] = []
    if not acceptance_authority.ready:
        records = [
            _authority_blocked_record(
                case_spec=spec,
                canonical_input=by_id[spec[1]],
                git_sha=git_sha,
                config=config,
                authority=acceptance_authority,
                preflight_path=preflight_path,
            )
            for spec in FORMAL_CASE_SPECS
        ]
    elif not formal_inputs_ready:
        records = [
            _formal_input_blocked_record(
                case_spec=spec,
                canonical_input=by_id[spec[1]],
                git_sha=git_sha,
                config=config,
                authority=acceptance_authority,
                eligibility=input_eligibility[spec[1]],
                preflight_path=preflight_path,
            )
            for spec in FORMAL_CASE_SPECS
        ]
    elif not preflight["ok"]:
        records = [
            _blocked_record(
                case_spec=spec,
                canonical_input=by_id[spec[1]],
                git_sha=git_sha,
                config=config,
                preflight=preflight,
                preflight_path=preflight_path,
                authority=acceptance_authority,
                formal_input=input_by_question[spec[1]],
            )
            for spec in FORMAL_CASE_SPECS
        ]
    else:
        assert acceptance_authority.frozen_model_policy is not None
        assert acceptance_authority.actual_requirement is not None
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
                    frozen_model_policy=acceptance_authority.frozen_model_policy,
                    actual_execution_requirement=(
                        acceptance_authority.actual_requirement
                    ),
                    formal_input=input_by_question[spec[1]],
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
            else "BLOCKED_AUTHORITY_REQUIRED"
            if not acceptance_authority.ready
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
            else "BLOCKED_AUTHORITY_REQUIRED"
            if not acceptance_authority.ready
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
        "formal_acceptance_authority": acceptance_authority.model_dump(mode="json"),
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
    "FormalAcceptanceAuthority",
    "FormalActualRunRecord",
    "FormalAuthorityEvidence",
    "FormalCaseEligibility",
    "FormalCaseInput",
    "FormalExecutionInput",
    "FormalImpactTrace",
    "FormalInputHashes",
    "FormalInputsEvidence",
    "FormalModelRouteAudit",
    "FormalMultimodalInput",
    "FormalPairingDecision",
    "FormalPairingMetadata",
    "FormalReviewerFeedbackBinding",
    "FormalRawResults",
    "FormalRevisionContextBinding",
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
    "assess_formal_case_input",
    "build_formal_readiness_status",
    "build_formal_impact_trace",
    "build_model_route_audit",
    "build_revision_context_binding",
    "build_metric004_evidence",
    "build_regression_matrix",
    "canonical_evidence_sha256",
    "canonical_sha256",
    "compute_formal_input_hashes",
    "execute_formal_case",
    "execution_result_hash",
    "execution_summary_hash",
    "load_selection_manifest",
    "load_canonical_catalog",
    "multimodal_artifact_hash",
    "multimodal_consumer_summary_hash",
    "reproduce_random_selection",
    "release_schema_bundle",
    "resolve_formal_acceptance_authority",
    "resolve_public_execution_result",
    "run_formal_release",
    "verify_captain_authority",
]
