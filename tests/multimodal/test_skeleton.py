"""T06 PR36：detect / adapters / vision schema / EvidenceCard→T04 / PDF / relative error."""

from __future__ import annotations

import json
from pathlib import Path

import pydantic
import pytest
from PIL import Image

from app.contracts.multimodal import MultimodalArtifact
from app.multimodal.adapters import (
    ChartAdapter,
    QwenVisionAdapter,
    TableAdapter,
    TimeseriesAdapter,
    get_adapter,
)
from app.multimodal.audit import VisionCallAuditStub
from app.multimodal.detect import detect_modality
from app.multimodal.errors import ExtractionError
from app.multimodal.eval_metrics import run_gold_evaluation
from app.multimodal.evidence_bridge import (
    artifact_to_evidence_card,
    low_confidence_blocks_fact,
)
from app.multimodal.evidence_live import index_multimodal_artifacts
from app.multimodal.evidence_rag import index_and_retrieve_via_t04_store
from app.multimodal.metrics_relative import evaluate_chart_series, relative_or_absolute_error
from app.multimodal.queue import MultimodalQueue, QueueRejection
from app.multimodal.qwen_vision import credential_status, run_qwen_vision
from app.multimodal.summary import build_consumer_summary
from app.multimodal.vision_schema import mock_vision_chart_response, parse_vision_chart_json
from app.multimodal.workflow_hook import build_revision_hook_payload

FIXTURES = Path(__file__).resolve().parent / "fixtures"
WAVE_B = FIXTURES / "wave_b"
PDF = WAVE_B / "pdf"


def _load_valid_table() -> MultimodalArtifact:
    payload = json.loads(
        (FIXTURES / "tables" / "sample_001.json").read_text(encoding="utf-8")
    )
    return MultimodalArtifact.model_validate(payload)


def _mock_chart_json(*, confidence: float = 0.88) -> str:
    return mock_vision_chart_response(
        legend=["run_a"],
        axes=[
            {
                "name": "x",
                "label": "time",
                "unit": "s",
                "min_value": 0.0,
                "max_value": 10.0,
            },
            {
                "name": "y",
                "label": "temperature",
                "unit": "K",
                "min_value": 270.0,
                "max_value": 310.0,
            },
        ],
        series=[
            {
                "name": "run_a",
                "points": [
                    {"x": 0, "y": 298.1},
                    {"x": 5, "y": 301.4},
                    {"x": 10, "y": 305.0},
                ],
            }
        ],
        confidence=confidence,
    )


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


def test_queue_rejects_failed_validation_status() -> None:
    failed = _load_valid_table().model_copy(update={"validation_status": "failed"})
    with pytest.raises(QueueRejection):
        MultimodalQueue().enqueue(failed)


def test_table_adapter_offline_fixture_packet() -> None:
    art = TableAdapter().process(str(WAVE_B / "tables" / "packet_001.json"))
    assert art.modality == "table"
    assert art.provenance.page == 2
    assert art.data.rows[0] == ["accuracy", "91.2", "91.2"]
    assert "#sha256=" in art.provenance.source_path
    card = artifact_to_evidence_card(art)
    assert "file_sha256" in card.locator


def test_table_adapter_real_pdf_extraction() -> None:
    art = TableAdapter().process(str(PDF / "sample_table.pdf"))
    assert art.provenance.source_type == "pdf"
    assert art.provenance.bbox is not None
    assert "#sha256=" in art.provenance.source_path
    assert "metric" in art.data.headers[0]
    assert any("91.2" in cell for row in art.data.rows for cell in row)
    # Units not reliably in sample PDF → must not claim high-confidence PASS
    assert art.validation_status == "needs_review"
    assert art.confidence < 0.80


def test_table_adapter_pdf_units_from_header_and_caller() -> None:
    # Inspect headers from PDF, then bind units using real column names.
    preview = TableAdapter().process(str(PDF / "sample_table.pdf"))
    bindings = [{"column": h, "unit": "%" if i else "name"} for i, h in enumerate(preview.data.headers)]
    art = TableAdapter().process(str(PDF / "sample_table.pdf"), column_units=bindings)
    assert art.column_units
    assert len(art.units) == len(art.data.headers)
    # With units present, confidence scoring may pass or still review on merges.
    assert art.validation_status in {"passed", "needs_review"}
    assert art.confidence >= 0.5
    assert "#sha256=" in art.provenance.source_path


def test_table_adapter_fail_closed_on_missing_bbox_and_bad_bbox() -> None:
    with pytest.raises(ExtractionError):
        TableAdapter().process(str(WAVE_B / "invalid" / "table_missing_bbox.json"))
    with pytest.raises(ExtractionError):
        TableAdapter().process(str(WAVE_B / "invalid" / "table_bad_bbox.json"))


def test_unlabeled_json_packet_rejected(tmp_path: Path) -> None:
    path = tmp_path / "table_unlabeled.json"
    path.write_text(
        json.dumps(
            {
                "page": 1,
                "bbox": {"x0": 1, "y0": 1, "x1": 2, "y1": 2},
                "headers": ["a"],
                "rows": [["1"]],
                "confidence": 0.9,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ExtractionError, match="input_kind"):
        TableAdapter().process(str(path))


def test_table_raster_image_fail_closed(tmp_path: Path) -> None:
    img = tmp_path / "scanned_table.png"
    Image.new("RGB", (32, 32), color=(255, 255, 255)).save(img)
    with pytest.raises(ExtractionError, match="vision path"):
        TableAdapter().process(str(img))


def test_table_packet_missing_units_needs_review(tmp_path: Path) -> None:
    path = tmp_path / "table_no_units.json"
    path.write_text(
        json.dumps(
            {
                "input_kind": "offline_fixture",
                "page": 1,
                "bbox": {"x0": 1, "y0": 1, "x1": 10, "y1": 10},
                "headers": ["a", "b"],
                "rows": [["1", "2"]],
                "confidence": 0.95,
                "legend": ["a", "b"],
            }
        ),
        encoding="utf-8",
    )
    art = TableAdapter().process(str(path))
    assert art.validation_status == "needs_review"
    assert art.confidence <= 0.79


def test_chart_adapter_packet_and_preprocessed_pdf() -> None:
    art = ChartAdapter().process(str(WAVE_B / "charts" / "packet_001.json"))
    assert art.legend == ["run_a"]
    pdf_art = ChartAdapter().process(str(PDF / "sample_chart.pdf"))
    # Demoted: NOT real vision chart parse
    assert pdf_art.provenance.source_type == "synthetic_fixture"
    assert pdf_art.confidence <= 0.79
    assert pdf_art.validation_status == "needs_review"
    assert len(pdf_art.data.rows) == 3
    assert "#sha256=" in pdf_art.provenance.source_path


def test_chart_adapter_raster_requires_vision(tmp_path: Path) -> None:
    img = tmp_path / "chart.png"
    Image.new("RGB", (64, 64), color=(240, 240, 240)).save(img)
    with pytest.raises(ExtractionError, match="Qwen vision"):
        ChartAdapter().process(str(img))


def test_chart_adapter_fail_closed_missing_legend_or_unit() -> None:
    with pytest.raises(ExtractionError):
        ChartAdapter().process(str(WAVE_B / "invalid" / "chart_missing_legend.json"))
    with pytest.raises(ExtractionError):
        ChartAdapter().process(str(WAVE_B / "invalid" / "chart_unknown_axis_unit.json"))


def test_timeseries_adapter_unit_convert_and_cleaning_log() -> None:
    adapter = TimeseriesAdapter()
    art = adapter.process(str(WAVE_B / "timeseries" / "sample_clean.csv"))
    assert art.data.rows[0][1] == "0.0001"
    assert any(r.action == "unit_convert" for r in adapter.last_cleaning_log or [])


def test_consumer_summary_from_skeleton_helper() -> None:
    artifact = _load_valid_table()
    summary = build_consumer_summary(artifact)
    assert summary.source_path == artifact.provenance.source_path


def test_vision_audit_stub_blocks_sensitive_markers() -> None:
    VisionCallAuditStub(
        call_id="c1", input_summary="page=1 chart crop", key_masked=True
    ).ensure_safe()
    with pytest.raises(ValueError):
        VisionCallAuditStub(
            call_id="c2",
            input_summary="api_key=REDACTED_SHOULD_STILL_FAIL",
            key_masked=True,
        ).ensure_safe()


def test_qwen_vision_phase_gate_denies_without_allow_actual() -> None:
    meta, audit = run_qwen_vision(str(PDF / "sample_chart.pdf"), allow_actual=False)
    assert audit.actual_external_call is False
    assert audit.status == "denied_no_paid_auth"
    assert audit.started_utc and audit.finished_utc
    assert audit.attempt_count == 1
    assert "DASHSCOPE_API_KEY" in meta["credential_status"]
    assert all(v in {"PRESENT", "MISSING"} for v in meta["credential_status"].values())


def test_qwen_adapter_preprocessed_pdf_demoted_when_denied() -> None:
    adapter = QwenVisionAdapter()
    art = adapter.process(str(PDF / "sample_chart.pdf"), allow_actual=False)
    assert art.modality == "chart"
    assert art.provenance.source_type == "synthetic_fixture"
    assert adapter.last_audit is not None
    assert adapter.last_audit.actual_external_call is False


def test_vision_schema_mock_success_and_fail_closed() -> None:
    good = parse_vision_chart_json(
        _mock_chart_json(),
        source_path="x.pdf",
        source_type="pdf",
        page=1,
        file_sha256="abc123",
    )
    assert good.legend == ["run_a"]
    assert good.axes is not None and len(good.axes) >= 2
    assert good.validation_status == "passed"
    with pytest.raises(ExtractionError, match="empty"):
        parse_vision_chart_json(
            "", source_path="x.pdf", source_type="pdf", page=1, file_sha256="a"
        )
    with pytest.raises(ExtractionError, match="JSON"):
        parse_vision_chart_json(
            "not-json", source_path="x.pdf", source_type="pdf", page=1, file_sha256="a"
        )
    bad_legend = json.loads(_mock_chart_json())
    bad_legend["legend"] = []
    with pytest.raises(ExtractionError, match="legend"):
        parse_vision_chart_json(
            json.dumps(bad_legend),
            source_path="x.pdf",
            source_type="pdf",
            page=1,
            file_sha256="a",
        )


def test_qwen_mock_success_png_and_no_fallback_discard(tmp_path: Path) -> None:
    img = tmp_path / "chart.webp"
    Image.new("RGB", (48, 48), color=(200, 200, 200)).save(img, format="WEBP")
    adapter = QwenVisionAdapter()
    art = adapter.process(
        str(img),
        allow_actual=False,
        mock_response_json=_mock_chart_json(confidence=0.9),
    )
    assert art.modality == "chart"
    assert art.legend == ["run_a"]
    assert "#sha256=" in art.provenance.source_path
    assert adapter.last_audit is not None
    assert adapter.last_audit.status == "success"
    assert adapter.last_audit.actual_external_call is False
    assert adapter.last_call_meta is not None
    assert adapter.last_call_meta.get("artifact") is not None


def test_qwen_mock_invalid_empty_timeout_auth(tmp_path: Path) -> None:
    img = tmp_path / "chart.jpg"
    Image.new("RGB", (40, 40), color=(180, 180, 180)).save(img, format="JPEG")
    adapter = QwenVisionAdapter()
    with pytest.raises(ExtractionError):
        adapter.process(str(img), mock_response_json="")
    with pytest.raises(ExtractionError):
        adapter.process(str(img), mock_response_json="{bad")
    with pytest.raises(ExtractionError, match="vision"):
        adapter.process(str(img), simulate_error="timeout", mock_response_json="{}")
    with pytest.raises(ExtractionError, match="vision"):
        adapter.process(str(img), simulate_error="auth", mock_response_json="{}")
    low = adapter.process(
        str(PDF / "sample_chart.pdf"),
        mock_response_json=_mock_chart_json(confidence=0.4),
    )
    assert low.validation_status == "failed"
    assert low_confidence_blocks_fact(low) is True


def test_qwen_refuses_silent_non_vision_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_VL_MODEL", "qwen-plus")
    from app.multimodal.qwen_vision import resolve_vision_model

    with pytest.raises(ExtractionError, match="vision model"):
        resolve_vision_model()


def test_relative_error_canonical_cases() -> None:
    exact = relative_or_absolute_error(1.0, 1.0)
    assert exact.pass_threshold and exact.relative_error == 0.0
    boundary = relative_or_absolute_error(1.05, 1.0)
    assert boundary.pass_threshold and abs((boundary.relative_error or 0) - 0.05) < 1e-12
    over = relative_or_absolute_error(1.0501, 1.0)
    assert not over.pass_threshold and over.needs_human_review
    zero_ok = relative_or_absolute_error(0.0, 0.0, zero_abs_tol=1e-6)
    assert zero_ok.pass_threshold and zero_ok.absolute_error == 0.0
    zero_bad = relative_or_absolute_error(1e-3, 0.0, zero_abs_tol=1e-6)
    assert not zero_bad.pass_threshold
    near_zero = relative_or_absolute_error(1.04e-8, 1e-8)
    assert near_zero.pass_threshold
    negative = relative_or_absolute_error(-1.04, -1.0)
    assert negative.pass_threshold
    nan_case = relative_or_absolute_error(float("nan"), 1.0)
    assert not nan_case.pass_threshold
    inf_case = relative_or_absolute_error(float("inf"), 1.0)
    assert not inf_case.pass_threshold
    multi = evaluate_chart_series(
        [["a", "0", "1.0"], ["b", "0", "-2.0"]],
        [["a", "0", "1.0"], ["b", "0", "-2.0"]],
    )
    assert multi["meets_threshold"] is True
    missing = evaluate_chart_series(
        [["a", "0", "1.0"]], [["a", "0", "1.0"], ["a", "1", "2.0"]]
    )
    assert missing["needs_human_review"] is True


def test_evidence_bundle_helper_not_t04_store() -> None:
    table = TableAdapter().process(str(WAVE_B / "tables" / "packet_001.json"))
    chart = ChartAdapter().process(str(PDF / "sample_chart.pdf"))
    ts = TimeseriesAdapter().process(str(WAVE_B / "timeseries" / "sample_clean.csv"))
    low = table.model_copy(
        update={
            "artifact_id": table.artifact_id + "-low",
            "confidence": 0.4,
            "validation_status": "needs_review",
        }
    )
    assert low_confidence_blocks_fact(low) is True
    index, bundle, meta = index_multimodal_artifacts([table, chart, ts, low])
    assert bundle.evidences
    assert meta["index_kind"].startswith("t06_evidence_bundle_helper")
    assert meta["supports_ids"] == []
    for eid in meta["consumed_evidence_ids"]:
        card = index.get(eid)
        assert card is not None
        assert "page" in card.locator and "source_path" in card.locator


def test_evidence_card_t04_memory_vector_store_e2e() -> None:
    """MultimodalArtifact → EvidenceCard → T04 MemoryVectorStore → retrieve."""
    table = TableAdapter().process(str(WAVE_B / "tables" / "packet_001.json"))
    chart = ChartAdapter().process(str(WAVE_B / "charts" / "packet_001.json"))
    low = table.model_copy(
        update={
            "artifact_id": table.artifact_id + "-low",
            "confidence": 0.4,
            "validation_status": "needs_review",
        }
    )
    result = index_and_retrieve_via_t04_store([table, chart, low])
    assert result["store"] == "app.rag.zvec_store.MemoryVectorStore"
    assert result["n_indexed"] == 3
    assert result["binary_in_prompt"] is False
    for item in result["retrieved"]:
        loc = item["locator"]
        assert "bbox" in loc or loc.get("page") is not None
        assert "units" in loc
        assert "confidence" in loc
        assert "validation_status" in loc
        assert "file_sha256" in loc or "sha256=" in str(loc.get("source_path", ""))
    # Low confidence must not support facts
    low_ids = {f"t06-{low.artifact_id}"}
    for sid in result["supports_ids"]:
        assert sid not in low_ids
    for item in result["retrieved"]:
        if item["evidence_id"] in low_ids:
            assert item["supports_fact"] is False


def test_minimal_e2e_queue_evidence_and_hook() -> None:
    arts = [
        TableAdapter().process(str(WAVE_B / "tables" / "packet_001.json")),
        ChartAdapter().process(str(WAVE_B / "charts" / "packet_001.json")),
        TimeseriesAdapter().process(str(WAVE_B / "timeseries" / "sample_clean.csv")),
    ]
    queue = MultimodalQueue()
    for art in arts:
        queue.enqueue(art)
        assert artifact_to_evidence_card(art).quoted_text
    payload = build_revision_hook_payload(queue.snapshot())
    assert len(payload["artifacts"]) == 3


def test_synthetic_gold_evaluation_uses_relative_error_and_blocks_actual() -> None:
    report = run_gold_evaluation()
    assert report["evaluation_kind"] == "synthetic_fixture_offline"
    assert "BLOCKED" in report["actual_zenodo_gold"]
    assert report["thresholds"]["chart_relative_error_max"] == 0.05
    assert report["thresholds"]["zero_abs_tol_declared"] is True
    assert "numeric_mae" not in json.dumps(report)
    assert report["overall"]["meets_threshold"] is True


def test_credential_status_names_only() -> None:
    status = credential_status()
    assert set(status) == {"DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "QWEN_VL_MODEL"}
    assert all(v in {"PRESENT", "MISSING"} for v in status.values())


def test_invalid_fixtures_fail_schema() -> None:
    for name in ("row_width_mismatch.json", "duplicate_headers.json"):
        payload = json.loads((FIXTURES / "invalid" / name).read_text(encoding="utf-8"))
        with pytest.raises(pydantic.ValidationError):
            MultimodalArtifact.model_validate(payload)


def test_sample_manifest_meets_per_category_minimum() -> None:
    manifest = json.loads((FIXTURES / "SAMPLE_MANIFEST.json").read_text(encoding="utf-8"))
    for category, meta in manifest["categories"].items():
        assert len(meta["sample_ids"]) >= meta["min_required"], category


def test_get_adapter_table() -> None:
    assert isinstance(get_adapter("table"), TableAdapter)
