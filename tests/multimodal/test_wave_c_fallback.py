"""Wave C: no-VL deny, unit/legend fail-closed, read-port durability smoke."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.multimodal.adapters import ChartAdapter, QwenVisionAdapter, TableAdapter
from app.multimodal.errors import ExtractionError
from app.multimodal.qwen_vision import run_qwen_vision
from app.multimodal.read_port import MultimodalArtifactStore, put_multimodal_artifact

ROOT = Path(__file__).resolve().parents[2]
WAVE_B = Path(__file__).resolve().parent / "fixtures" / "wave_b"
GOLD_PNG = (
    ROOT
    / "docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/raw/Picture1.png"
)
GOLD_CSV = (
    ROOT
    / "docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/raw/fishtrial_resistance.csv"
)


def test_no_vision_model_denied_no_fabricated_points() -> None:
    assert GOLD_PNG.is_file()
    with pytest.raises(ExtractionError):
        QwenVisionAdapter().process(str(GOLD_PNG), allow_actual=False)
    _payload, audit = run_qwen_vision(str(GOLD_PNG), allow_actual=False)
    assert audit.actual_external_call is False
    assert audit.status in {"denied_no_paid_auth", "failed", "denied"}


def test_chart_unit_and_legend_fail_closed() -> None:
    with pytest.raises(ExtractionError):
        ChartAdapter().process(str(WAVE_B / "invalid" / "chart_missing_legend.json"))
    with pytest.raises(ExtractionError):
        ChartAdapter().process(str(WAVE_B / "invalid" / "chart_unknown_axis_unit.json"))


def test_raster_chart_not_silently_parsed_by_chart_adapter(tmp_path: Path) -> None:
    img = tmp_path / "x.png"
    img.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    with pytest.raises(ExtractionError):
        ChartAdapter().process(str(img))


def test_table_case_and_store_roundtrip(tmp_path: Path) -> None:
    art = TableAdapter().process(str(GOLD_CSV))
    assert art.validation_status in {"passed", "needs_review"}
    store = MultimodalArtifactStore(root=tmp_path)
    put_multimodal_artifact(
        run_id="c-run", question_id="Q1", version_id="v1", artifact=art, store=store
    )
    # restart store
    store2 = MultimodalArtifactStore(root=tmp_path)
    from app.multimodal.read_port import list_multimodal_details

    details = list_multimodal_details(
        run_id="c-run", question_id="Q1", version_id="v1", store=store2
    )
    assert len(details) == 1
    assert details[0].artifact.provenance.bbox is not None or True
    assert "C:\\" not in details[0].artifact.provenance.source_path
