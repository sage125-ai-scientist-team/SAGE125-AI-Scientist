"""T06 PR-A：detect / queue / adapter / audit 骨架测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pydantic
import pytest

from app.contracts.multimodal import MultimodalArtifact
from app.multimodal.adapters import TableAdapter, get_adapter
from app.multimodal.audit import VisionCallAuditStub
from app.multimodal.detect import detect_modality
from app.multimodal.queue import MultimodalQueue, QueueRejection
from app.multimodal.summary import build_consumer_summary

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load_valid_table() -> MultimodalArtifact:
    payload = json.loads(
        (FIXTURES / "tables" / "sample_001.json").read_text(encoding="utf-8")
    )
    return MultimodalArtifact.model_validate(payload)


def test_detect_modality_by_extension_and_hint() -> None:
    assert detect_modality("data/run.csv") == "timeseries"
    assert detect_modality("paper.pdf") == "chart"
    assert detect_modality("table.json") == "table"
    assert detect_modality("unknown.bin", hint="table") == "table"
    with pytest.raises(ValueError):
        detect_modality("unknown.bin")


def test_queue_accepts_valid_artifact_and_rejects_invalid() -> None:
    queue = MultimodalQueue()
    valid = _load_valid_table()
    queued = queue.enqueue(valid)
    assert len(queue) == 1
    assert queued.artifact_id == valid.artifact_id

    with pytest.raises(QueueRejection):
        queue.enqueue(
            {
                "artifact_id": "bad",
                "modality": "table",
                "provenance": {
                    "source_path": "x",
                    "source_type": "synthetic_fixture",
                    "page": 1,
                },
                "data": {"headers": ["a", "a"], "rows": [["1", "2"]]},
                "confidence": 0.5,
                "validation_status": "needs_review",
            }
        )
    assert len(queue) == 1


def test_queue_rejects_failed_validation_status() -> None:
    queue = MultimodalQueue()
    failed = _load_valid_table().model_copy(update={"validation_status": "failed"})
    with pytest.raises(QueueRejection):
        queue.enqueue(failed)


def test_adapter_skeleton_is_not_implemented() -> None:
    adapter = get_adapter("table")
    assert isinstance(adapter, TableAdapter)
    with pytest.raises(NotImplementedError):
        adapter.process("tests/multimodal/fixtures/tables/sample_001.json")


def test_consumer_summary_from_skeleton_helper() -> None:
    artifact = _load_valid_table()
    summary = build_consumer_summary(artifact)
    assert summary.source_path == artifact.provenance.source_path
    assert summary.confidence == artifact.confidence
    assert summary.validation_status == artifact.validation_status
    assert summary.units == artifact.units


def test_vision_audit_stub_blocks_sensitive_markers() -> None:
    ok = VisionCallAuditStub(
        call_id="c1",
        input_summary="page=1 chart crop",
        key_masked=True,
    ).ensure_safe()
    assert ok.status == "not_implemented"
    with pytest.raises(ValueError):
        VisionCallAuditStub(
            call_id="c2",
            input_summary="api_key=REDACTED_SHOULD_STILL_FAIL",
            key_masked=True,
        ).ensure_safe()


def test_invalid_fixtures_fail_schema() -> None:
    for name in ("row_width_mismatch.json", "duplicate_headers.json"):
        payload = json.loads(
            (FIXTURES / "invalid" / name).read_text(encoding="utf-8")
        )
        with pytest.raises(pydantic.ValidationError):
            MultimodalArtifact.model_validate(payload)


def test_sample_manifest_meets_per_category_minimum() -> None:
    manifest = json.loads(
        (FIXTURES / "SAMPLE_MANIFEST.json").read_text(encoding="utf-8")
    )
    for category, meta in manifest["categories"].items():
        assert len(meta["sample_ids"]) >= meta["min_required"], category
