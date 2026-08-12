"""Tests for T06 production multimodal read port (T08 owner confirmation)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts.multimodal import (
    BoundingBox,
    MultimodalArtifact,
    Provenance,
    TableData,
)
from app.multimodal.read_port import (
    T06_LOW_CONFIDENCE_THRESHOLD,
    MultimodalArtifactStore,
    MultimodalPortError,
    list_multimodal_artifacts,
    list_multimodal_details,
    put_multimodal_artifact,
)


def _artifact(
    *,
    artifact_id: str,
    modality: str = "table",
    confidence: float = 0.95,
    validation_status: str = "passed",
    source_path: str = r"C:\secret\data\sample_table.pdf#sha256=abc",
) -> MultimodalArtifact:
    return MultimodalArtifact(
        artifact_id=artifact_id,
        modality=modality,  # type: ignore[arg-type]
        provenance=Provenance(
            source_path=source_path,
            source_type="pdf",
            page=1,
            bbox=BoundingBox(x0=10.0, y0=20.0, x1=110.0, y1=220.0),
        ),
        units=["ohm"],
        column_units=[],
        axes=None,
        legend=["R"],
        data=TableData(headers=["t", "R"], rows=[["1", "2.0"], ["2", "2.1"]]),
        confidence=confidence,
        validation_status=validation_status,  # type: ignore[arg-type]
    )


def test_put_list_roundtrip_preserves_bbox_units_status(tmp_path: Path) -> None:
    store = MultimodalArtifactStore(root=tmp_path)
    art = _artifact(artifact_id="a-table-1", confidence=0.91)
    put_multimodal_artifact(
        run_id="run-1",
        question_id="Q001",
        version_id="v1",
        artifact=art,
        store=store,
    )
    listed = list_multimodal_artifacts(
        run_id="run-1", question_id="Q001", version_id="v1", store=store
    )
    assert len(listed) == 1
    got = listed[0]
    assert got.artifact_id == "a-table-1"
    assert got.provenance.bbox is not None
    assert got.provenance.bbox.x0 == 10.0
    assert got.units == ["ohm"]
    assert got.confidence == 0.91
    assert got.validation_status == "passed"
    # Absolute path must not leak
    assert "C:\\secret" not in got.provenance.source_path
    assert got.provenance.source_path.startswith("t06-source:")


def test_list_details_marks_low_confidence_review(tmp_path: Path) -> None:
    store = MultimodalArtifactStore(root=tmp_path)
    art = _artifact(
        artifact_id="a-low",
        confidence=T06_LOW_CONFIDENCE_THRESHOLD - 0.01,
        validation_status="passed",
    )
    put_multimodal_artifact(
        run_id="run-2", question_id="Q002", version_id="v1", artifact=art, store=store
    )
    details = list_multimodal_details(
        run_id="run-2", question_id="Q002", version_id="v1", store=store
    )
    assert len(details) == 1
    assert details[0].needs_human_review is True
    assert details[0].public_source.bbox is not None
    assert details[0].public_source.coordinate_space == "pdf_user_space"
    assert details[0].public_source.preview_artifact_id == "a-low"


def test_empty_identity_returns_empty_not_error(tmp_path: Path) -> None:
    store = MultimodalArtifactStore(root=tmp_path)
    assert (
        list_multimodal_artifacts(
            run_id="run-x", question_id="Q999", version_id="v0", store=store
        )
        == []
    )


def test_invalid_identity_rejected(tmp_path: Path) -> None:
    store = MultimodalArtifactStore(root=tmp_path)
    with pytest.raises(MultimodalPortError) as exc:
        list_multimodal_artifacts(
            run_id="../evil", question_id="Q1", version_id="v1", store=store
        )
    assert exc.value.category == "invalid_contract"


def test_restart_durable_read(tmp_path: Path) -> None:
    store1 = MultimodalArtifactStore(root=tmp_path)
    put_multimodal_artifact(
        run_id="run-3",
        question_id="Q003",
        version_id="v2",
        artifact=_artifact(artifact_id="persist-1"),
        store=store1,
    )
    # New store instance simulates process restart on same root.
    store2 = MultimodalArtifactStore(root=tmp_path)
    listed = list_multimodal_artifacts(
        run_id="run-3", question_id="Q003", version_id="v2", store=store2
    )
    assert [a.artifact_id for a in listed] == ["persist-1"]


def test_modalities_table_chart_timeseries(tmp_path: Path) -> None:
    store = MultimodalArtifactStore(root=tmp_path)
    for mid, modality in [
        ("t1", "table"),
        ("c1", "chart"),
        ("s1", "timeseries"),
    ]:
        put_multimodal_artifact(
            run_id="run-m",
            question_id="Q010",
            version_id="v1",
            artifact=_artifact(artifact_id=mid, modality=modality),
            store=store,
        )
    arts = list_multimodal_artifacts(
        run_id="run-m", question_id="Q010", version_id="v1", store=store
    )
    assert {a.modality for a in arts} == {"table", "chart", "timeseries"}
    assert all(a.provenance.bbox is not None for a in arts)
