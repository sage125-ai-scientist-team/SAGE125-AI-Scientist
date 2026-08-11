"""Wave B deterministic per-question mutable-state isolation sidecar."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Mapping

from app.batch.checkpoint import resume_job
from app.batch.errors import BatchRunnerError
from app.contracts.batch import (
    BatchJob,
    CheckpointRecord,
    ResumePolicy,
)


ISOLATION_VERSION = "t07.isolation.v1"
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class QuestionIsolationIdentity:
    """Immutable sidecar bound to one Wave A job input snapshot."""

    batch_id: str
    question_id: str
    source_hash: str
    input_hash: str
    workspace: str
    context_id: str
    memory_namespace: str
    cache_namespace: str
    prompt_namespace: str
    isolation_version: str = ISOLATION_VERSION

    def __post_init__(self) -> None:
        _require_segment(self.batch_id, "batch_id")
        _require_segment(self.question_id, "question_id")
        _require_sha256(self.source_hash, "source_hash")
        _require_sha256(self.input_hash, "input_hash")
        for name in (
            "workspace",
            "context_id",
            "memory_namespace",
            "cache_namespace",
            "prompt_namespace",
            "isolation_version",
        ):
            _require_text(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class QuestionScopedResult:
    """Attempt result that remains bound to its source and question input."""

    question_id: str
    source_hash: str
    input_hash: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        _require_segment(self.question_id, "previous_result.question_id")
        _require_sha256(self.source_hash, "previous_result.source_hash")
        _require_sha256(self.input_hash, "previous_result.input_hash")
        if not isinstance(self.payload, Mapping):
            raise TypeError("previous_result.payload must be a mapping")


@dataclass(slots=True)
class QuestionExecutionContext:
    """Attempt-local mutable containers owned by one frozen identity."""

    identity: QuestionIsolationIdentity
    memory: dict[str, Any] = field(default_factory=dict)
    cache: dict[str, Any] = field(default_factory=dict)
    prompt_context: dict[str, Any] = field(default_factory=dict)
    previous_result: QuestionScopedResult | None = None


def build_isolation_identity(job: BatchJob) -> QuestionIsolationIdentity:
    """Build a sidecar while preserving Wave A workspace/context/cache keys."""

    if not isinstance(job, BatchJob):
        raise TypeError("job must be a BatchJob")
    derived = _derive_identity_fields(
        batch_id=job.batch_id,
        question_id=job.question_id,
        source_hash=job.source_hash,
        input_hash=job.input_hash,
        isolation_version=ISOLATION_VERSION,
    )
    wave_a_mismatches = [
        field_name
        for field_name in ("workspace", "context_id", "cache_namespace")
        if getattr(job, field_name) != derived[field_name]
    ]
    if wave_a_mismatches:
        raise BatchRunnerError(
            "ISOLATION_JOB_FIELDS_MISMATCH",
            (
                "BatchJob isolation fields do not match Wave A derivation: "
                f"{wave_a_mismatches}"
            ),
        )
    return QuestionIsolationIdentity(**derived)


def create_isolated_context(
    identity: QuestionIsolationIdentity,
    *,
    prompt_context: Mapping[str, Any] | None = None,
    previous_result: QuestionScopedResult | None = None,
) -> QuestionExecutionContext:
    """Create fresh state and reject cross-question previous results."""

    _validate_identity_derivation(identity)
    if prompt_context is not None and not isinstance(prompt_context, Mapping):
        raise TypeError("prompt_context must be a mapping")
    if previous_result is not None:
        _validate_previous_result(identity, previous_result)
        previous_result = QuestionScopedResult(
            question_id=previous_result.question_id,
            source_hash=previous_result.source_hash,
            input_hash=previous_result.input_hash,
            payload=deepcopy(dict(previous_result.payload)),
        )
    return QuestionExecutionContext(
        identity=identity,
        memory={},
        cache={},
        prompt_context=deepcopy(dict(prompt_context or {})),
        previous_result=previous_result,
    )


def validate_isolation_boundary(
    contexts: list[QuestionExecutionContext]
    | tuple[QuestionExecutionContext, ...],
) -> None:
    """Fail closed on namespace collisions and mutable-object aliasing."""

    namespace_owners: dict[str, dict[str, str]] = {
        name: {}
        for name in (
            "workspace",
            "context_id",
            "memory_namespace",
            "cache_namespace",
            "prompt_namespace",
        )
    }
    mutable_objects: dict[int, tuple[str, str]] = {}
    for context in contexts:
        if not isinstance(context, QuestionExecutionContext):
            raise TypeError("contexts must contain QuestionExecutionContext")
        identity = context.identity
        _validate_identity_derivation(identity)
        if context.previous_result is not None:
            _validate_previous_result(identity, context.previous_result)

        for field_name, owners in namespace_owners.items():
            value = getattr(identity, field_name)
            previous_owner = owners.get(value)
            if previous_owner is not None and previous_owner != identity.question_id:
                raise BatchRunnerError(
                    f"{field_name.upper()}_COLLISION",
                    (
                        f"{field_name} is shared by {previous_owner} and "
                        f"{identity.question_id}: {value}"
                    ),
                )
            owners[value] = identity.question_id

        for field_name in ("memory", "cache", "prompt_context"):
            marker = id(getattr(context, field_name))
            previous = mutable_objects.get(marker)
            current = (identity.question_id, field_name)
            if previous is not None and previous != current:
                raise BatchRunnerError(
                    "MUTABLE_STATE_ALIAS",
                    (
                        f"Mutable {field_name} for {identity.question_id} "
                        f"aliases {previous[1]} owned by {previous[0]}"
                    ),
                )
            mutable_objects[marker] = current


def reset_mutable_question_state(
    context: QuestionExecutionContext,
) -> QuestionExecutionContext:
    """Clear attempt state without changing its identity."""

    if not isinstance(context, QuestionExecutionContext):
        raise TypeError("context must be a QuestionExecutionContext")
    identity = context.identity
    context.memory.clear()
    context.cache.clear()
    context.prompt_context.clear()
    context.previous_result = None
    if context.identity != identity:
        raise BatchRunnerError(
            "IDENTITY_MUTATED_DURING_RESET",
            "reset_mutable_question_state changed immutable identity",
        )
    return context


def validate_retry_scope(
    identity: QuestionIsolationIdentity,
    checkpoint: CheckpointRecord,
    expected_job: BatchJob,
    policy: ResumePolicy,
) -> BatchJob:
    """Delegate retry compatibility to Wave A and verify the sidecar identity."""

    expected_identity = build_isolation_identity(expected_job)
    if identity != expected_identity:
        raise BatchRunnerError(
            "ISOLATION_IDENTITY_MISMATCH",
            "Isolation identity does not match the expected Wave A job",
        )
    restored = resume_job(checkpoint, expected_job, policy)
    if build_isolation_identity(restored) != identity:
        raise BatchRunnerError(
            "RETRY_ISOLATION_IDENTITY_MISMATCH",
            "Restored job does not match the expected isolation identity",
        )
    return restored


def _validate_identity_derivation(identity: QuestionIsolationIdentity) -> None:
    if not isinstance(identity, QuestionIsolationIdentity):
        raise TypeError("identity must be a QuestionIsolationIdentity")
    expected = QuestionIsolationIdentity(
        **_derive_identity_fields(
            batch_id=identity.batch_id,
            question_id=identity.question_id,
            source_hash=identity.source_hash,
            input_hash=identity.input_hash,
            isolation_version=identity.isolation_version,
        )
    )
    if identity != expected:
        raise BatchRunnerError(
            "ISOLATION_IDENTITY_INVALID",
            "Isolation fields do not match their deterministic derivation",
        )


def _validate_previous_result(
    identity: QuestionIsolationIdentity,
    result: QuestionScopedResult,
) -> None:
    comparisons = (
        (
            "question_id",
            result.question_id,
            identity.question_id,
            "PREVIOUS_RESULT_QUESTION_MISMATCH",
        ),
        (
            "source_hash",
            result.source_hash,
            identity.source_hash,
            "PREVIOUS_RESULT_SOURCE_HASH_MISMATCH",
        ),
        (
            "input_hash",
            result.input_hash,
            identity.input_hash,
            "PREVIOUS_RESULT_INPUT_HASH_MISMATCH",
        ),
    )
    for field_name, actual, expected, error_code in comparisons:
        if actual != expected:
            raise BatchRunnerError(
                error_code,
                f"previous_result {field_name} does not match current question",
            )


def _derive_identity_fields(
    *,
    batch_id: str,
    question_id: str,
    source_hash: str,
    input_hash: str,
    isolation_version: str,
) -> dict[str, str]:
    normalized_batch = _require_segment(batch_id, "batch_id")
    normalized_question = _require_segment(question_id, "question_id")
    normalized_source_hash = _require_sha256(source_hash, "source_hash")
    normalized_input_hash = _require_sha256(input_hash, "input_hash")
    normalized_version = _require_text(isolation_version, "isolation_version")
    seed = json.dumps(
        {
            "batch_id": normalized_batch,
            "input_hash": normalized_input_hash,
            "isolation_version": normalized_version,
            "question_id": normalized_question,
            "source_hash": normalized_source_hash,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest_prefix = hashlib.sha256(seed).hexdigest()[:20]
    input_prefix = normalized_input_hash[:16]
    readable_scope = f"{normalized_batch}:{normalized_question}:{digest_prefix}"
    return {
        "batch_id": normalized_batch,
        "question_id": normalized_question,
        "source_hash": normalized_source_hash,
        "input_hash": normalized_input_hash,
        "workspace": PurePosixPath(
            normalized_batch,
            normalized_question,
            "workspace",
        ).as_posix(),
        "context_id": (
            f"ctx:{normalized_batch}:{normalized_question}:{input_prefix}"
        ),
        "memory_namespace": f"memory:{readable_scope}",
        "cache_namespace": (
            f"cache:{normalized_batch}:{normalized_question}:{input_prefix}"
        ),
        "prompt_namespace": f"prompt:{readable_scope}",
        "isolation_version": normalized_version,
    }


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_segment(value: Any, field_name: str) -> str:
    normalized = _require_text(value, field_name)
    if not SAFE_SEGMENT.fullmatch(normalized):
        raise ValueError(f"{field_name} must be one safe path segment")
    return normalized


def _require_sha256(value: Any, field_name: str) -> str:
    normalized = _require_text(value, field_name)
    if not SHA256.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase SHA-256")
    return normalized
