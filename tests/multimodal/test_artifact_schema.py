"""
T06 PR-A：MultimodalArtifact 契约测试。

覆盖合法构造/序列化，以及重复表头、行宽、缺失溯源、越界置信度、
额外字段、未知列单位映射等红灯规则。
"""

from __future__ import annotations

import json
from pathlib import Path

import pydantic
import pytest

from app.contracts.multimodal import MultimodalArtifact, to_consumer_summary

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _valid_table_kwargs(**overrides: object) -> dict:
    """返回一套合法 table 构造参数，可用 overrides 覆盖个别字段。"""
    base: dict = {
        "artifact_id": "mm-table-001",
        "modality": "table",
        "provenance": {
            "source_path": "tests/multimodal/fixtures/tables/sample_001.json",
            "source_type": "synthetic_fixture",
            "page": 1,
            "bbox": {"x0": 72.0, "y0": 400.0, "x1": 540.0, "y1": 720.0},
        },
        "units": ["%", "n"],
        "axes": None,
        "legend": ["group_a", "group_b"],
        "data": {
            "headers": ["metric", "group_a", "group_b"],
            "rows": [
                ["accuracy", "91.2", "88.5"],
                ["sample_size", "120", "115"],
            ],
        },
        "confidence": 0.86,
        "validation_status": "needs_review",
    }
    base.update(overrides)
    return base


def test_table_multimodal_artifact_serializes_to_json() -> None:
    """A complete table MultimodalArtifact must construct and serialize to JSON."""
    artifact = MultimodalArtifact(**_valid_table_kwargs())

    payload = artifact.model_dump(mode="json")
    encoded = json.dumps(payload)

    assert isinstance(encoded, str)
    assert payload["artifact_id"] == "mm-table-001"
    assert payload["modality"] == "table"
    assert payload["provenance"]["page"] == 1
    assert payload["units"] == ["%", "n"]
    assert payload["confidence"] == 0.86
    assert payload["validation_status"] == "needs_review"
    roundtrip = json.loads(encoded)
    assert roundtrip["data"]["headers"][0] == "metric"
    reloaded = MultimodalArtifact.model_validate(roundtrip)
    assert reloaded.artifact_id == artifact.artifact_id


def test_table_artifact_rejects_row_width_mismatch() -> None:
    """Rows whose width differs from the header count must raise ValidationError."""
    with pytest.raises(pydantic.ValidationError):
        MultimodalArtifact(
            **_valid_table_kwargs(
                artifact_id="mm-table-bad-width-001",
                data={
                    "headers": ["metric", "value"],
                    "rows": [
                        ["accuracy", "91.2"],
                        ["sample_size"],
                    ],
                },
                units=["%"],
                legend=["group_a"],
                confidence=0.5,
            )
        )


def test_table_artifact_rejects_duplicate_headers() -> None:
    """Exact duplicate header names must raise ValidationError (ambiguous columns)."""
    with pytest.raises(pydantic.ValidationError):
        MultimodalArtifact(
            **_valid_table_kwargs(
                artifact_id="mm-table-dup-headers-001",
                data={
                    "headers": ["time_s", "time_s"],
                    "rows": [["0", "1"]],
                },
                units=["s", "s"],
                legend=["series_a"],
                confidence=0.5,
            )
        )


def test_artifact_rejects_blank_source_path() -> None:
    """Blank provenance.source_path must be rejected as missing source info."""
    with pytest.raises(pydantic.ValidationError):
        MultimodalArtifact(
            **_valid_table_kwargs(
                provenance={
                    "source_path": "   ",
                    "source_type": "synthetic_fixture",
                    "page": 1,
                }
            )
        )


def test_artifact_rejects_missing_provenance() -> None:
    """Omitting provenance entirely must raise ValidationError."""
    kwargs = _valid_table_kwargs()
    del kwargs["provenance"]
    with pytest.raises(pydantic.ValidationError):
        MultimodalArtifact(**kwargs)


def test_artifact_rejects_confidence_out_of_range() -> None:
    """confidence outside [0, 1] must raise ValidationError."""
    with pytest.raises(pydantic.ValidationError):
        MultimodalArtifact(**_valid_table_kwargs(confidence=1.5))
    with pytest.raises(pydantic.ValidationError):
        MultimodalArtifact(**_valid_table_kwargs(confidence=-0.01))


def test_artifact_rejects_undeclared_extra_fields() -> None:
    """Undeclared top-level fields must be rejected (extra=forbid)."""
    with pytest.raises(pydantic.ValidationError):
        MultimodalArtifact(**_valid_table_kwargs(secret_token="should-not-pass"))


def test_artifact_rejects_column_units_unknown_column() -> None:
    """column_units referencing a missing header must raise ValidationError."""
    with pytest.raises(pydantic.ValidationError):
        MultimodalArtifact(
            **_valid_table_kwargs(
                column_units=[{"column": "not_a_real_column", "unit": "m"}]
            )
        )


def test_consumer_summary_keeps_source_units_confidence_status() -> None:
    """Downstream summary must retain source, units, confidence, validation_status."""
    artifact = MultimodalArtifact(
        **_valid_table_kwargs(
            column_units=[
                {"column": "group_a", "unit": "%"},
                {"column": "group_b", "unit": "%"},
            ]
        )
    )
    summary = to_consumer_summary(artifact)
    payload = summary.model_dump(mode="json")
    assert payload["source_path"] == artifact.provenance.source_path
    assert payload["units"] == ["%", "n"]
    assert payload["confidence"] == 0.86
    assert payload["validation_status"] == "needs_review"
    assert payload["header_count"] == 3
    assert payload["row_count"] == 2
    assert "data" not in payload


def test_fixture_samples_load_as_valid_artifacts() -> None:
    """Manifest-listed legal fixtures must validate as MultimodalArtifact."""
    manifest_path = FIXTURES / "SAMPLE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for sample in manifest["samples"]:
        if sample.get("expected") != "valid":
            continue
        path = FIXTURES / sample["path"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        artifact = MultimodalArtifact.model_validate(payload)
        assert artifact.modality == sample["modality"]
        assert artifact.artifact_id == sample["artifact_id"]
