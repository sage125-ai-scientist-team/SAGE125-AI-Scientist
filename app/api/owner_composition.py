"""T08 thin adapters for frozen T01, T03 and T06 owner ports.

The adapters in this module translate transport-neutral owner contracts into
API-owned projections.  They deliberately do not read owner-private tables,
scan artifact directories, recompute scientific decisions, or restore truth
flags from untrusted serialized data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import ValidationError

from app.api.contracts import MultimodalDetailProjection
from app.api.upstream import FilesystemQuestionOwnerAdapter
from app.contracts.evidence import EvidenceBundle
from app.evidence.read_port import (
    EvidencePortError,
    get_evidence_bundle as get_t01_evidence_bundle,
)
from app.feedback import (
    DefaultFeedbackService,
    FeedbackConflict,
    FeedbackPermissionDenied,
    FeedbackStorageError,
    FeedbackStore,
    FeedbackSubmission,
    InvalidFeedbackInput,
    UnsafeFeedbackInput,
)
from app.multimodal.read_port import (
    MultimodalArtifactStore,
    MultimodalPortError,
    list_multimodal_details,
)


OwnerFailureCategory = Literal[
    "invalid_input",
    "unsafe_input",
    "permission_denied",
    "conflict",
    "identity_mismatch",
    "unavailable",
    "not_found",
    "not_ready",
    "invalid_contract",
    "resource_conflict",
    "read_failed",
]
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


class OwnerPortFailure(RuntimeError):
    """Safe owner-port failure translated by the HTTP route layer."""

    def __init__(
        self,
        *,
        component: str,
        category: OwnerFailureCategory,
        retryable: bool,
    ) -> None:
        super().__init__(f"{component}:{category}")
        self.component = component
        self.category = category
        self.retryable = retryable


@dataclass(frozen=True)
class FeedbackSubmissionResult:
    """Minimal immutable result required by the T08 feedback receipt."""

    feedback_id: str
    target_version_id: str
    correlation_id: str


@runtime_checkable
class FeedbackSubmitPort(Protocol):
    """API-facing subset of the frozen T03 feedback service."""

    def submit(
        self,
        *,
        job_id: str,
        run_id: str,
        question_id: str,
        target_version_id: str,
        feedback: str,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
    ) -> FeedbackSubmissionResult: ...


@dataclass(frozen=True)
class _RequestBoundSubmitAuthorizer:
    """Authorize exactly one authenticated job identity and no decisions."""

    actor_id: str
    run_id: str
    question_id: str

    def authorize(
        self,
        *,
        action: Literal["submit", "decide"],
        actor_id: str,
        run_id: str,
        question_id: str,
    ) -> bool:
        """Return true only for the request identity checked by the API route."""
        return (
            action == "submit"
            and actor_id == self.actor_id
            and run_id == self.run_id
            and question_id == self.question_id
        )


@runtime_checkable
class EvidenceBundleReader(Protocol):
    """Frozen callable shape exported by the T01 production read port."""

    def __call__(
        self,
        *,
        run_id: str,
        question_id: str,
    ) -> EvidenceBundle: ...


@runtime_checkable
class EvidenceReadPort(Protocol):
    """API-facing subset of the frozen T01 evidence read port."""

    def get_evidence_bundle(
        self,
        *,
        run_id: str,
        question_id: str,
    ) -> EvidenceBundle: ...


class T01EvidenceReadAdapter:
    """Read EvidenceBundle only through T01's public callable.

    本适配器不得打开 T01 SQLite schema、扫描 ``evidence_cards.json``，
    也不得把 fixture 或旧 exports 包装成生产成功。
    """

    _COMPONENT = "T01 EvidenceBundle"
    _CATEGORY_MAP: dict[str, OwnerFailureCategory] = {
        "not_found": "not_found",
        "not_ready": "not_ready",
        "invalid_contract": "invalid_contract",
        "identity_mismatch": "identity_mismatch",
        "conflict": "resource_conflict",
        "retryable_upstream_failure": "read_failed",
        "non_retryable_upstream_failure": "read_failed",
        "unavailable": "unavailable",
    }

    def __init__(
        self,
        reader: EvidenceBundleReader | None = None,
    ) -> None:
        """
        绑定 T01 公开读函数。

        参数：
            reader: 可选测试注入。缺省为
                ``app.evidence.read_port.get_evidence_bundle``。
        """
        self._reader = reader or get_t01_evidence_bundle

    def get_evidence_bundle(
        self,
        *,
        run_id: str,
        question_id: str,
    ) -> EvidenceBundle:
        """
        按 ``run_id + question_id`` 读取权威 EvidenceBundle。

        参数：
            run_id: 已绑定的上游运行 ID。
            question_id: 当前任务题目 ID。

        返回：
            再次 Schema 校验后的 ``EvidenceBundle``。

        异常：
            OwnerPortFailure: 按 T01 category 映射，不透传路径或异常原文。
        """
        try:
            payload = self._reader(
                run_id=run_id,
                question_id=question_id,
            )
        except EvidencePortError as exc:
            category = self._CATEGORY_MAP.get(exc.category, "invalid_contract")
            raise OwnerPortFailure(
                component=self._COMPONENT,
                category=category,
                retryable=bool(exc.retryable),
            ) from None
        try:
            return EvidenceBundle.model_validate(payload)
        except (TypeError, ValueError, ValidationError) as exc:
            raise OwnerPortFailure(
                component=self._COMPONENT,
                category="invalid_contract",
                retryable=False,
            ) from exc


class ComposedOwnerContractAdapter(FilesystemQuestionOwnerAdapter):
    """Compose T07 questions with the T01 evidence port.

    T02 versions/diff stay fail-closed on the inherited filesystem adapter
    until a frozen production read port exists.
    """

    def __init__(
        self,
        questions_path: str | Path,
        *,
        evidence_port: EvidenceReadPort | None = None,
    ) -> None:
        """
        组装默认生产读端口。

        参数：
            questions_path: T07 ``QuestionItem`` JSON 路径。
            evidence_port: 可选 T01 适配器；缺省 ``T01EvidenceReadAdapter``。
        """
        super().__init__(questions_path)
        self._evidence_port = evidence_port or T01EvidenceReadAdapter()

    def get_evidence_bundle(
        self,
        *,
        run_id: str,
        question_id: str,
    ) -> EvidenceBundle:
        """
        委托 T01 组合端口，不读取文件系统证据夹具。

        参数：
            run_id: 已绑定的上游运行 ID。
            question_id: 当前任务题目 ID。

        返回：
            T01 权威 ``EvidenceBundle``。
        """
        return self._evidence_port.get_evidence_bundle(
            run_id=run_id,
            question_id=question_id,
        )


class T03FeedbackSubmitAdapter:
    """Submit authenticated feedback through the frozen T03 service."""

    def __init__(self, store: FeedbackStore) -> None:
        self._store = store

    def submit(
        self,
        *,
        job_id: str,
        run_id: str,
        question_id: str,
        target_version_id: str,
        feedback: str,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
    ) -> FeedbackSubmissionResult:
        """Persist one idempotent submission without deciding its disposition."""
        authorizer = _RequestBoundSubmitAuthorizer(
            actor_id=actor_id,
            run_id=run_id,
            question_id=question_id,
        )
        service = DefaultFeedbackService(self._store, authorizer=authorizer)
        try:
            record = service.submit_request(
                FeedbackSubmission(
                    run_id=run_id,
                    question_id=question_id,
                    target_version_id=target_version_id,
                    feedback=feedback,
                    source={"channel": "api", "actor_id": actor_id},
                    correlation_id=correlation_id,
                    idempotency_key=idempotency_key,
                    metadata={"job_id": job_id},
                )
            )
        except UnsafeFeedbackInput as exc:
            raise OwnerPortFailure(
                component="T03 FeedbackService",
                category="unsafe_input",
                retryable=False,
            ) from exc
        except InvalidFeedbackInput as exc:
            raise OwnerPortFailure(
                component="T03 FeedbackService",
                category="invalid_input",
                retryable=False,
            ) from exc
        except FeedbackPermissionDenied as exc:
            raise OwnerPortFailure(
                component="T03 FeedbackService",
                category="permission_denied",
                retryable=False,
            ) from exc
        except FeedbackConflict as exc:
            raise OwnerPortFailure(
                component="T03 FeedbackService",
                category="conflict",
                retryable=False,
            ) from exc
        except FeedbackStorageError as exc:
            raise OwnerPortFailure(
                component="T03 FeedbackService",
                category="unavailable",
                retryable=True,
            ) from exc
        return FeedbackSubmissionResult(
            feedback_id=record.feedback_id,
            target_version_id=record.target_version_id,
            correlation_id=record.correlation_id,
        )


@runtime_checkable
class MultimodalReadPort(Protocol):
    """API-facing projection of the frozen T06 detail read port."""

    def list_details(
        self,
        *,
        run_id: str,
        question_id: str,
        version_id: str,
    ) -> list[MultimodalDetailProjection]: ...


class T06MultimodalReadAdapter:
    """Project T06 owner details without dropping provenance or review flags."""

    def __init__(self, store: MultimodalArtifactStore | None = None) -> None:
        self._store = store

    @staticmethod
    def _require_public_locator(detail: Any) -> None:
        """Reject owner projections that still contain local path syntax."""
        label = str(detail.public_source.source_label)
        locator = str(detail.artifact.provenance.source_path)
        unsafe_label = (
            "/" in label
            or "\\" in label
            or _WINDOWS_ABSOLUTE_PATH.match(label) is not None
        )
        unsafe_locator = (
            not locator.startswith("t06-source:")
            or _WINDOWS_ABSOLUTE_PATH.search(locator) is not None
            or "\\" in locator
        )
        if unsafe_label or unsafe_locator:
            raise OwnerPortFailure(
                component="T06 MultimodalDetailView",
                category="unavailable",
                retryable=False,
            )

    def list_details(
        self,
        *,
        run_id: str,
        question_id: str,
        version_id: str,
    ) -> list[MultimodalDetailProjection]:
        """Read the frozen three-key T06 port and preserve its public fields."""
        try:
            details = list_multimodal_details(
                run_id=run_id,
                question_id=question_id,
                version_id=version_id,
                store=self._store,
            )
            for detail in details:
                self._require_public_locator(detail)
            return [
                MultimodalDetailProjection(
                    artifact_id=detail.artifact.artifact_id,
                    modality=detail.artifact.modality,
                    source_id=detail.public_source.source_id,
                    source_label=detail.public_source.source_label,
                    preview_artifact_id=detail.public_source.preview_artifact_id,
                    coordinate_space=detail.public_source.coordinate_space,
                    page=detail.public_source.page,
                    bbox=(
                        None
                        if detail.public_source.bbox is None
                        else detail.public_source.bbox.model_dump(mode="json")
                    ),
                    extracted_values=detail.artifact.data.model_dump(mode="json"),
                    units=list(detail.artifact.units),
                    column_units=[
                        item.model_dump(mode="json")
                        for item in detail.artifact.column_units
                    ],
                    axes=(
                        []
                        if detail.artifact.axes is None
                        else [
                            item.model_dump(mode="json")
                            for item in detail.artifact.axes
                        ]
                    ),
                    legend=list(detail.artifact.legend),
                    confidence=detail.artifact.confidence,
                    validation_status=detail.artifact.validation_status,
                    needs_human_review=detail.needs_human_review,
                )
                for detail in details
            ]
        except MultimodalPortError as exc:
            category: OwnerFailureCategory
            if exc.category == "invalid_contract":
                category = "invalid_input"
            elif exc.category == "identity_mismatch":
                category = "identity_mismatch"
            else:
                category = "unavailable"
            raise OwnerPortFailure(
                component="T06 MultimodalDetailView",
                category=category,
                retryable=bool(exc.retryable),
            ) from exc
        except (ValidationError, TypeError, ValueError, KeyError) as exc:
            raise OwnerPortFailure(
                component="T06 MultimodalDetailView",
                category="unavailable",
                retryable=False,
            ) from exc


__all__ = [
    "ComposedOwnerContractAdapter",
    "EvidenceBundleReader",
    "EvidenceReadPort",
    "FeedbackSubmissionResult",
    "FeedbackSubmitPort",
    "MultimodalReadPort",
    "OwnerPortFailure",
    "T01EvidenceReadAdapter",
    "T03FeedbackSubmitAdapter",
    "T06MultimodalReadAdapter",
]
