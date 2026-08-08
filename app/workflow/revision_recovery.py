"""Durable idempotency and recovery boundary for T02 revision events."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.execution import ExecutionResult
from app.contracts.revision import IssueClosure, PlanVersion
from app.workflow.explainable_revision import (
    RevisionExecutionController,
    RevisionExecutionState,
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


RevisionEventType = Literal[
    "reviewer_callback",
    "revision_event",
    "execution_result",
]
RevisionEventStatus = Literal["in_progress", "completed", "failed"]


class RevisionEventRecord(BaseModel):
    """One durable event claim and its terminal outcome, if present."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    event_type: RevisionEventType
    status: RevisionEventStatus = "in_progress"
    version_id: str | None = None
    failure_reason: str | None = None

    @model_validator(mode="after")
    def _validate_outcome(self) -> "RevisionEventRecord":
        if self.status == "in_progress" and (
            self.version_id is not None or self.failure_reason is not None
        ):
            raise ValueError("in-progress event cannot carry a terminal outcome")
        if self.event_type in {"reviewer_callback", "revision_event"}:
            if self.status == "completed" and self.version_id is None:
                raise ValueError("completed version event requires version_id")
            if self.failure_reason is not None:
                raise ValueError("version event cannot carry execution failure")
        if self.event_type == "execution_result" and self.version_id is not None:
            raise ValueError("execution result event cannot carry version_id")
        if self.status == "failed" and not (self.failure_reason or "").strip():
            raise ValueError("failed event requires failure_reason")
        return self


class VersionEventResult(BaseModel):
    """Idempotent result returned for a version-producing callback."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: PlanVersion
    created: bool
    duplicate: bool
    resumed: bool


class RevisionRecoveryCheckpoint(BaseModel):
    """Self-hashed complete recovery state for one bounded revision run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    controller: RevisionExecutionState
    versions: tuple[PlanVersion, ...] = ()
    events: tuple[RevisionEventRecord, ...] = ()
    issue_closures: tuple[IssueClosure, ...] = ()
    checkpoint_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    def hash_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"checkpoint_hash"})

    @model_validator(mode="after")
    def _validate_checkpoint(self) -> "RevisionRecoveryCheckpoint":
        version_ids = tuple(version.version_id for version in self.versions)
        if version_ids != self.controller.version_ids:
            raise ValueError(
                "controller version lineage must match persisted versions"
            )
        for index, version in enumerate(self.versions):
            if version.run_id != self.controller.run_id:
                raise ValueError("persisted version run_id must match controller")
            expected_parent = None if index == 0 else self.versions[index - 1].version_id
            if version.parent_version_id != expected_parent:
                raise ValueError("persisted versions require contiguous lineage")
        event_ids = tuple(event.event_id for event in self.events)
        if event_ids != self.controller.processed_event_ids:
            raise ValueError("controller event lineage must match persisted events")
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("persisted event IDs must be unique")
        known_versions = set(version_ids)
        for event in self.events:
            if event.version_id is not None and event.version_id not in known_versions:
                raise ValueError("event references a missing plan version")
        issue_ids = [issue.issue_id for issue in self.issue_closures]
        if len(set(issue_ids)) != len(issue_ids):
            raise ValueError("persisted issue IDs must be unique")
        if any(issue.status == "resolved" for issue in self.issue_closures):
            if f"{self.controller.run_id}:v2" not in known_versions:
                raise ValueError("resolved issues require generated V2")
        if self.controller.status == "completed" and (
            f"{self.controller.run_id}:v2" not in known_versions
        ):
            raise ValueError("completed revision checkpoint requires generated V2")
        expected_hash = _sha256(self.hash_payload())
        if self.checkpoint_hash != expected_hash:
            raise ValueError("revision recovery checkpoint hash does not match")
        return self

    @classmethod
    def create(
        cls,
        *,
        controller: RevisionExecutionState,
        versions: Sequence[PlanVersion],
        events: Sequence[RevisionEventRecord],
        issue_closures: Sequence[IssueClosure],
    ) -> "RevisionRecoveryCheckpoint":
        payload = {
            "schema_version": 1,
            "controller": controller.model_dump(mode="json"),
            "versions": [version.model_dump(mode="json") for version in versions],
            "events": [event.model_dump(mode="json") for event in events],
            "issue_closures": [
                issue.model_dump(mode="json") for issue in issue_closures
            ],
        }
        return cls.model_validate(
            {**payload, "checkpoint_hash": _sha256(payload)}
        )


class RevisionRecoveryCoordinator:
    """Atomically bind event IDs to versions and retain retry-safe state."""

    def __init__(
        self,
        *,
        controller: RevisionExecutionController,
        versions: Sequence[PlanVersion] = (),
        events: Sequence[RevisionEventRecord] = (),
        issue_closures: Sequence[IssueClosure] = (),
    ) -> None:
        self.controller = controller
        self._versions = [version.model_copy(deep=True) for version in versions]
        self._events = [event.model_copy(deep=True) for event in events]
        self._issue_closures = [
            issue.model_copy(deep=True) for issue in issue_closures
        ]

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        issue_closures: Sequence[IssueClosure] = (),
        max_iterations: int = 2,
        max_retries: int = 1,
    ) -> "RevisionRecoveryCoordinator":
        return cls(
            controller=RevisionExecutionController.create(
                run_id=run_id,
                max_iterations=max_iterations,
                max_retries=max_retries,
            ),
            issue_closures=issue_closures,
        )

    @property
    def issue_closures(self) -> tuple[IssueClosure, ...]:
        return tuple(issue.model_copy(deep=True) for issue in self._issue_closures)

    def list_versions(self) -> list[PlanVersion]:
        return [version.model_copy(deep=True) for version in self._versions]

    def _event_index(self, event_id: str) -> int | None:
        for index, event in enumerate(self._events):
            if event.event_id == event_id:
                return index
        return None

    def _replace_event(self, index: int, **updates: Any) -> None:
        payload = self._events[index].model_dump(mode="json")
        payload.update(updates)
        self._events[index] = RevisionEventRecord.model_validate(payload)

    def begin_event(
        self,
        event_id: str,
        event_type: RevisionEventType,
    ) -> Literal["started", "resumed", "duplicate"]:
        normalized = event_id.strip()
        if not normalized:
            raise ValueError("event_id cannot be blank")
        index = self._event_index(normalized)
        if index is not None:
            existing = self._events[index]
            if existing.event_type != event_type:
                raise ValueError("event_id cannot change event_type")
            return "duplicate" if existing.status != "in_progress" else "resumed"
        if self.controller.state.status != "active":
            raise ValueError("new events require an active revision")
        if not self.controller.claim_event(normalized):
            raise ValueError("controller contains an unbound processed event")
        self._events.append(
            RevisionEventRecord(event_id=normalized, event_type=event_type)
        )
        return "started"

    def apply_version_event(
        self,
        *,
        event_id: str,
        event_type: Literal["reviewer_callback", "revision_event"],
        version: PlanVersion,
    ) -> VersionEventResult:
        if not isinstance(version, PlanVersion):
            raise TypeError("version must be a PlanVersion instance")
        normalized = event_id.strip()
        disposition = self.begin_event(normalized, event_type)
        event_index = self._event_index(normalized)
        assert event_index is not None
        event = self._events[event_index]

        if disposition == "duplicate":
            if event.version_id != version.version_id:
                raise ValueError("duplicate event cannot produce a different version")
            stored = next(
                item for item in self._versions if item.version_id == event.version_id
            )
            if stored.model_dump(mode="json") != version.model_dump(mode="json"):
                raise ValueError("duplicate event version content does not match")
            return VersionEventResult(
                version=stored.model_copy(deep=True),
                created=False,
                duplicate=True,
                resumed=False,
            )

        if self.controller.state.status != "active":
            raise ValueError("resumed version events require an active revision")

        if version.run_id != self.controller.state.run_id:
            raise ValueError("version run_id must match recovery controller")
        existing = next(
            (item for item in self._versions if item.version_id == version.version_id),
            None,
        )
        if existing is not None:
            if existing.model_dump(mode="json") != version.model_dump(mode="json"):
                raise ValueError("persisted version content does not match resumed event")
            owner = next(
                (
                    item
                    for item in self._events
                    if item.version_id == version.version_id
                    and item.event_id != normalized
                ),
                None,
            )
            if owner is not None:
                raise ValueError("plan version is already bound to another event")
            self._replace_event(
                event_index,
                status="completed",
                version_id=version.version_id,
            )
            return VersionEventResult(
                version=existing.model_copy(deep=True),
                created=False,
                duplicate=False,
                resumed=True,
            )

        expected_number = len(self._versions) + 1
        expected_id = f"{self.controller.state.run_id}:v{expected_number}"
        expected_parent = (
            None if not self._versions else self._versions[-1].version_id
        )
        if version.version_id != expected_id or version.parent_version_id != expected_parent:
            raise ValueError("version event must extend contiguous plan lineage")

        self.controller.record_version(version.version_id)
        self._versions.append(version.model_copy(deep=True))
        self._replace_event(
            event_index,
            status="completed",
            version_id=version.version_id,
        )
        return VersionEventResult(
            version=version.model_copy(deep=True),
            created=True,
            duplicate=False,
            resumed=disposition == "resumed",
        )

    def set_issue_closures(self, issues: Sequence[IssueClosure]) -> None:
        snapshots = [issue.model_copy(deep=True) for issue in issues]
        if self.controller.state.status in {"completed", "stopped"} and [
            item.model_dump(mode="json") for item in snapshots
        ] != [
            item.model_dump(mode="json") for item in self._issue_closures
        ]:
            raise ValueError("terminal revision issue state is immutable")
        ids = [issue.issue_id for issue in snapshots]
        if len(ids) != len(set(ids)):
            raise ValueError("issue closure IDs must be unique")
        previous_ids = {issue.issue_id for issue in self._issue_closures}
        if not previous_ids.issubset(ids):
            raise ValueError("issue closure update cannot drop existing issue IDs")
        if any(issue.status == "resolved" for issue in snapshots):
            if f"{self.controller.state.run_id}:v2" not in {
                item.version_id for item in self._versions
            }:
                raise ValueError("resolved issues require generated V2")
        previous_by_id = {issue.issue_id: issue for issue in self._issue_closures}
        has_v2 = f"{self.controller.state.run_id}:v2" in {
            item.version_id for item in self._versions
        }
        for issue in snapshots:
            previous = previous_by_id.get(issue.issue_id)
            if previous is None and (
                not has_v2
                or issue.status != "open"
                or issue.opened_in_version != 2
            ):
                raise ValueError(
                    "new revision issues must enter open in generated V2"
                )
            if previous is not None and (
                issue.category != previous.category
                or issue.description != previous.description
                or issue.opened_in_version != previous.opened_in_version
            ):
                raise ValueError("issue identity fields cannot change")
            if previous is not None and previous.status == "resolved" and issue.status == "open":
                raise ValueError("resolved issue cannot be reopened")
            if issue.status == "resolved" and not (issue.resolution_note or "").strip():
                raise ValueError("resolved issue requires closure reason")
            if issue.status == "resolved" and issue.closed_in_version != 2:
                raise ValueError("resolved issue must close in generated V2")
        self._issue_closures = snapshots

    def record_execution_result(
        self,
        result: ExecutionResult,
    ) -> Literal["succeeded", "retry", "stopped", "duplicate"]:
        if not isinstance(result, ExecutionResult):
            raise TypeError("result must be an ExecutionResult instance")
        if result.status in {"planned", "running"}:
            raise ValueError("execution result must be terminal")
        event_id = f"execution:{result.execution_id}"
        disposition = self.begin_event(event_id, "execution_result")
        event_index = self._event_index(event_id)
        assert event_index is not None
        if disposition == "duplicate":
            return "duplicate"
        if result.status == "succeeded":
            self._replace_event(event_index, status="completed")
            return "succeeded"
        detail = (
            f"{result.error.code}:{result.error.message}"
            if result.error is not None
            else result.status
        )
        reason = f"execution:{result.status}:{detail}"
        outcome = self.controller.record_failure(reason)
        self._replace_event(
            event_index,
            status="failed",
            failure_reason=reason,
        )
        return outcome

    def checkpoint(self) -> RevisionRecoveryCheckpoint:
        return RevisionRecoveryCheckpoint.create(
            controller=self.controller.state,
            versions=self._versions,
            events=self._events,
            issue_closures=self._issue_closures,
        )

    def serialize(self) -> str:
        return _canonical_json(self.checkpoint().model_dump(mode="json"))

    @classmethod
    def deserialize(
        cls,
        payload: str | bytes | Mapping[str, Any],
    ) -> "RevisionRecoveryCoordinator":
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        raw = json.loads(payload) if isinstance(payload, str) else dict(payload)
        checkpoint = RevisionRecoveryCheckpoint.model_validate(raw)
        return cls(
            controller=RevisionExecutionController(checkpoint.controller),
            versions=checkpoint.versions,
            events=checkpoint.events,
            issue_closures=checkpoint.issue_closures,
        )
