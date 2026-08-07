"""T06 Wave B：detect / queue / adapter / audit / EvidenceCard / eval 测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pydantic
import pytest

from app.contracts.multimodal import MultimodalArtifact
from app.multimodal.adapters import (
    ChartAdapter,
    QwenVisionAdapter,
    TableAdapter,
    TimeseriesAdapter,
    get_adapter,
)
from app.multimodal.audit import VisionCallAuditStub, run_vision_or_deny
from app.multimodal.detect import detect_modality
from app.multimodal.errors import ExtractionError
from app.multimodal.eval_metrics import run_gold_evaluation
from app.multimodal.evidence_bridge import (
    artifact_to_evidence_card,
    low_confidence_blocks_fact,
)
from app.multimodal.queue import MultimodalQueue, QueueRejection
from app.multimodal.summary import build_consumer_summary
from app.multimodal.workflow_hook import build_revision_hook_payload

FIXTURES = Path(__file__).resolve().parent / "fixtures"
WAVE_B = FIXTURES / "wave_b"


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


def test_table_adapter_extracts_merged_cells_and_provenance() -> None:
    adapter = get_adapter("table")
    assert isinstance(adapter, TableAdapter)
    art = adapter.process(str(WAVE_B / "tables" / "packet_001.json"))
    assert art.modality == "table"
    assert art.provenance.page == 2
    assert art.provenance.bbox is not None
    assert art.data.rows[0] == ["accuracy", "91.2", "91.2"]
    assert art.validation_status == "passed"
    assert art.column_units[0].unit == "%"


def test_table_adapter_fail_closed_on_missing_bbox_and_bad_bbox() -> None:
    adapter = TableAdapter()
    with pytest.raises(ExtractionError):
        adapter.process(str(WAVE_B / "invalid" / "table_missing_bbox.json"))
    with pytest.raises(ExtractionError):
        adapter.process(str(WAVE_B / "invalid" / "table_bad_bbox.json"))


def test_chart_adapter_extracts_axes_legend_and_points() -> None:
    art = ChartAdapter().process(str(WAVE_B / "charts" / "packet_001.json"))
    assert art.modality == "chart"
    assert art.legend == ["run_a"]
    assert art.axes is not None and len(art.axes) == 2
    assert len(art.data.rows) == 3
    assert art.validation_status == "passed"


def test_chart_adapter_fail_closed_missing_legend_or_unit() -> None:
    with pytest.raises(ExtractionError):
        ChartAdapter().process(str(WAVE_B / "invalid" / "chart_missing_legend.json"))
    with pytest.raises(ExtractionError):
        ChartAdapter().process(
            str(WAVE_B / "invalid" / "chart_unknown_axis_unit.json")
        )


def test_timeseries_adapter_unit_convert_and_cleaning_log() -> None:
    adapter = TimeseriesAdapter()
    art = adapter.process(str(WAVE_B / "timeseries" / "sample_clean.csv"))
    assert art.modality == "timeseries"
    assert art.data.rows[0][1] == "0.0001"
    assert adapter.last_cleaning_log
    assert any(r.action == "unit_convert" for r in adapter.last_cleaning_log)


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


def test_qwen_vision_denies_paid_call_and_falls_back_offline() -> None:
    payload, audit = run_vision_or_deny("unused")
    assert payload == {}
    assert audit.actual_external_call is False
    assert audit.status == "denied_no_paid_auth"
    adapter = QwenVisionAdapter()
    art = adapter.process(str(WAVE_B / "charts" / "packet_001.json"))
    assert art.validation_status == "needs_review"
    assert adapter.last_audit is not None
    assert adapter.last_audit.actual_external_call is False


def test_evidence_card_bridge_preserves_locator_and_blocks_low_confidence() -> None:
    art = TableAdapter().process(str(WAVE_B / "tables" / "packet_001.json"))
    card = artifact_to_evidence_card(art)
    assert card.locator["page"] == 2
    assert "bbox" in card.locator
    assert card.verification_status != "valid"
    low = art.model_copy(update={"confidence": 0.4, "validation_status": "needs_review"})
    assert low_confidence_blocks_fact(low) is True
    hook = build_revision_hook_payload([art, low])
    assert hook["binary_in_prompt"] is False
    assert hook["human_review_required"] is True
    assert any(not x["supports_fact"] for x in hook["artifacts"])


def test_minimal_e2e_queue_evidence_and_hook() -> None:
    table = TableAdapter().process(str(WAVE_B / "tables" / "packet_001.json"))
    chart = ChartAdapter().process(str(WAVE_B / "charts" / "packet_001.json"))
    ts = TimeseriesAdapter().process(str(WAVE_B / "timeseries" / "sample_clean.csv"))
    queue = MultimodalQueue()
    for art in (table, chart, ts):
        queue.enqueue(art)
        card = artifact_to_evidence_card(art)
        assert card.locator["modality"] == art.modality
        assert card.quoted_text
    payload = build_revision_hook_payload(queue.snapshot())
    assert len(payload["artifacts"]) == 3
    assert payload["schema_version"] == "t06-workflow-hook-v1"


def test_synthetic_gold_evaluation_runs_and_labels_actual_blocked() -> None:
    report = run_gold_evaluation()
    assert report["evaluation_kind"] == "synthetic_fixture_offline"
    assert "BLOCKED" in report["actual_zenodo_gold"]
    assert report["overall"]["cases_ok"] == 3
    assert report["overall"]["meets_threshold"] is True


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
