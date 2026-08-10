"""T08 read ports for frozen T01/T02/T07 owner contracts.

The API layer depends on this port instead of owner implementation details or
artifact naming conventions.  Adapters validate every payload at the boundary;
they never infer evidence provenance, issue closure, or version differences.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.batch import JobStatus as BatchJobStatus
from app.contracts.evidence import EvidenceBundle
from app.contracts.revision import PlanVersion
from app.core.schemas import QuestionItem


class OwnerReadError(RuntimeError):
    """Base class for owner read failures mapped by the HTTP adapter."""


class OwnerContractUnavailable(OwnerReadError):
    def __init__(self, component: str) -> None:
        super().__init__(component)
        self.component = component


class OwnerResourceNotFound(OwnerReadError):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(f"{resource}: {identifier}")
        self.resource = resource
        self.identifier = identifier


class OwnerContractInvalid(OwnerReadError):
    def __init__(self, component: str, message: str) -> None:
        super().__init__(message)
        self.component = component


class QuestionOwnerRecord(BaseModel):
    """T07 question projection plus optional owner-supplied status."""

    model_config = ConfigDict(extra="forbid")

    item: QuestionItem
    status: BatchJobStatus | None = None
    status_reason: str | None = None


class OwnerVersionDiff(BaseModel):
    """Structured diff supplied by T02; T08 must not synthesize this object."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    from_version_id: str = Field(min_length=1)
    to_version_id: str = Field(min_length=1)
    changes: list[dict[str, Any]] = Field(default_factory=list)
    issue_changes: list[dict[str, Any]] = Field(default_factory=list)
    score_delta: dict[str, float] = Field(default_factory=dict)
    stop_reason: str | None = None


class OwnerContractReadPort(Protocol):
    """Read-only boundary consumed by T08 v1 routes."""

    def list_questions(self) -> list[QuestionOwnerRecord]: ...

    def get_evidence_bundle(self, run_id: str) -> EvidenceBundle: ...

    def list_plan_versions(self, run_id: str) -> list[PlanVersion]: ...

    def get_version_diff(
        self,
        run_id: str,
        from_version_id: str,
        to_version_id: str,
    ) -> OwnerVersionDiff: ...


def _question_record(payload: Mapping[str, Any]) -> QuestionOwnerRecord:
    raw = dict(payload)
    status = raw.pop("status", None)
    status_reason = raw.pop("status_reason", None)
    question_id = raw.pop("question_id", None)
    if question_id is not None:
        if "id" in raw and raw["id"] != question_id:
            raise ValueError("question_id does not match QuestionItem.id")
        raw.setdefault("id", question_id)
    return QuestionOwnerRecord(
        item=QuestionItem.model_validate(raw),
        status=status,
        status_reason=(str(status_reason) if status_reason is not None else None),
    )


class FilesystemQuestionOwnerAdapter:
    """Read the canonical question source while leaving other owners explicit."""

    def __init__(self, questions_path: str | Path) -> None:
        self.questions_path = Path(questions_path)

    def list_questions(self) -> list[QuestionOwnerRecord]:
        if not self.questions_path.exists():
            raise OwnerContractUnavailable("T07 QuestionItem")
        try:
            payload = json.loads(self.questions_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("question source must be a JSON array")
            return [_question_record(item) for item in payload]
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise OwnerContractInvalid("T07 QuestionItem", str(exc)) from exc

    def get_evidence_bundle(self, run_id: str) -> EvidenceBundle:
        del run_id
        raise OwnerContractUnavailable("T01 EvidenceBundle")

    def list_plan_versions(self, run_id: str) -> list[PlanVersion]:
        del run_id
        raise OwnerContractUnavailable("T02 PlanVersion/IssueClosure")

    def get_version_diff(
        self,
        run_id: str,
        from_version_id: str,
        to_version_id: str,
    ) -> OwnerVersionDiff:
        del run_id, from_version_id, to_version_id
        raise OwnerContractUnavailable("T02 structured version diff")


class FixtureOwnerContractAdapter:
    """Strict in-memory adapter for contract and integration fixtures.

    It is also useful to wire an already validated owner service response in a
    composition root.  Stored models are copied on read so callers cannot mutate
    the adapter's source of truth.
    """

    def __init__(
        self,
        *,
        questions: Sequence[QuestionOwnerRecord],
        evidence_by_run: Mapping[str, EvidenceBundle],
        versions_by_run: Mapping[str, Sequence[PlanVersion]],
        diffs_by_run: Mapping[tuple[str, str, str], OwnerVersionDiff],
    ) -> None:
        self._questions = [item.model_copy(deep=True) for item in questions]
        self._evidence_by_run = {
            key: value.model_copy(deep=True) for key, value in evidence_by_run.items()
        }
        self._versions_by_run = {
            key: [item.model_copy(deep=True) for item in value]
            for key, value in versions_by_run.items()
        }
        self._diffs_by_run = {
            key: value.model_copy(deep=True) for key, value in diffs_by_run.items()
        }

    @classmethod
    def from_payloads(
        cls,
        *,
        questions: Sequence[Mapping[str, Any]],
        evidence_by_run: Mapping[str, Mapping[str, Any]],
        versions_by_run: Mapping[str, Sequence[Mapping[str, Any]]],
        diffs_by_run: Mapping[tuple[str, str, str], Mapping[str, Any]],
    ) -> "FixtureOwnerContractAdapter":
        return cls(
            questions=[_question_record(item) for item in questions],
            evidence_by_run={
                run_id: EvidenceBundle.model_validate(payload)
                for run_id, payload in evidence_by_run.items()
            },
            versions_by_run={
                run_id: [PlanVersion.model_validate(item) for item in payload]
                for run_id, payload in versions_by_run.items()
            },
            diffs_by_run={
                key: OwnerVersionDiff.model_validate(payload)
                for key, payload in diffs_by_run.items()
            },
        )

    def list_questions(self) -> list[QuestionOwnerRecord]:
        return [item.model_copy(deep=True) for item in self._questions]

    def get_evidence_bundle(self, run_id: str) -> EvidenceBundle:
        try:
            return self._evidence_by_run[run_id].model_copy(deep=True)
        except KeyError:
            raise OwnerResourceNotFound("evidence_bundle", run_id) from None

    def list_plan_versions(self, run_id: str) -> list[PlanVersion]:
        try:
            versions = self._versions_by_run[run_id]
        except KeyError:
            raise OwnerResourceNotFound("plan_versions", run_id) from None
        return [item.model_copy(deep=True) for item in versions]

    def get_version_diff(
        self,
        run_id: str,
        from_version_id: str,
        to_version_id: str,
    ) -> OwnerVersionDiff:
        key = (run_id, from_version_id, to_version_id)
        try:
            return self._diffs_by_run[key].model_copy(deep=True)
        except KeyError:
            identifier = f"{run_id}:{from_version_id}:{to_version_id}"
            raise OwnerResourceNotFound("version_diff", identifier) from None
