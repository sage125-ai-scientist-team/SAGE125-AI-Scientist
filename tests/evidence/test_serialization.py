"""
T01 Wave C：125 输出序列化与 API 样例可 JSON 往返。
"""

import json

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)
from app.evidence.citation_renderer import build_citation_item
from app.evidence.quality_gate import run_quality_gate
from app.evidence.serialization import (
    build_api_example_payload,
    build_output_envelope_v125,
    dumps_output_envelope,
    serialize_evidence_bundle,
)


def _card() -> EvidenceCardContract:
    """
    构造序列化测试用证据卡。

    返回：
        EvidenceCardContract。
    """
    return EvidenceCardContract(
        evidence_id="EV-SER",
        source_id="src",
        source_type="paper",
        title="Serialization demo",
        quoted_text="Quoted body used for serialization completeness checks.",
        locator={"page": 4, "section": "Methods"},
        authors=["Ada"],
        year=2022,
        doi="10.1234/ser.demo",
        content_hash="sha256:ser",
        domain="medicine",
    )


def test_bundle_and_envelope_are_json_serializable():
    """全部证据字段可序列化，且确定性 dumps 可往返。"""
    card = _card()
    bundle = EvidenceBundle(
        bundle_id="B-SER",
        evidences=[card],
        links=[
            ClaimEvidenceLink(
                claim_id="C1",
                evidence_id="EV-SER",
                relation="supports",
                claim_domain="medicine",
            )
        ],
    )
    quality = run_quality_gate(bundle)
    citations = [
        build_citation_item(
            claim_id="C1",
            card=card,
            support_status="allow",
        )
    ]
    envelope = build_output_envelope_v125(
        bundle=bundle,
        citations=citations,
        quality=quality,
    )
    text = dumps_output_envelope(envelope)
    loaded = json.loads(text)
    assert loaded["schema_version"] == "t01-output-envelope-v125"
    assert loaded["bundle"]["evidences"][0]["quoted_text"]
    assert loaded["bundle"]["deterministic_digest"]
    dumped = serialize_evidence_bundle(bundle)
    assert dumped["evidences"][0]["evidence_id"] == "EV-SER"
    assert len(dumped["deterministic_digest"]) == 64


def test_api_example_for_t08():
    """T08 API 样例包含 markdown 与 citations。"""
    example = build_api_example_payload(claim_id="C1", card=_card())
    assert example["consumer"] == "T08"
    assert example["example"]["citations"]
    assert "EV-SER" in example["example"]["markdown"]
