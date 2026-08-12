"""Gate0 fixture package smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts.multimodal import MultimodalArtifact

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "docs/modules/T06/gate0_fixtures"


def test_gate0_manifest_lists_four_kinds() -> None:
    man = json.loads((FIX / "MANIFEST.json").read_text(encoding="utf-8"))
    kinds = {f["kind"] for f in man["fixtures"]}
    assert kinds == {
        "validated",
        "low_confidence_manual_review",
        "missing_provenance",
        "invalid",
    }
    assert man["public_import_path"].endswith("list_multimodal_artifacts")


def test_gate0_validated_and_lowconf_are_valid_artifacts() -> None:
    for name in ("validated.json", "low_confidence_manual_review.json"):
        payload = json.loads((FIX / name).read_text(encoding="utf-8"))
        assert payload["evidence_class"] == "mock"
        art = MultimodalArtifact.model_validate(payload["artifact"])
        assert art.provenance.bbox is not None
        assert "confidence" in payload["fields_for_t08"]
        assert "needs_human_review" in payload["fields_for_t08"]


def test_gate0_missing_provenance_expected_rejects() -> None:
    payload = json.loads((FIX / "missing_provenance.json").read_text(encoding="utf-8"))
    assert payload["evidence_class"] == "expected"
    with pytest.raises(ValidationError):
        MultimodalArtifact.model_validate(payload["invalid_payload_example"])


def test_gate0_invalid_bbox_expected_rejects() -> None:
    payload = json.loads((FIX / "invalid.json").read_text(encoding="utf-8"))
    assert payload["evidence_class"] == "expected"
    with pytest.raises(ValidationError):
        MultimodalArtifact.model_validate(payload["invalid_payload_example"])
