"""
T01 Wave B（08/01）：引用渲染器与 T08 payload 测试。
"""

from app.contracts.evidence import EvidenceCardContract
from app.evidence.citation_renderer import (
    build_citation_item,
    build_t08_citation_payload,
    evidence_anchor_id,
    normalize_source_url,
    render_citation_markdown,
    render_claim_to_evidence_jump,
)
from app.evidence.gold_set import gold_set_count, load_evidence_gold_set
from app.evidence.support_checker import SupportDecision


def _card() -> EvidenceCardContract:
    """构造带 DOI 与 locator 的契约卡。"""
    return EvidenceCardContract(
        evidence_id="EV-CITE-1",
        source_id="10.1234/demo",
        source_type="paper",
        title="Demo oncology paper",
        quoted_text="EGFR inhibition improves response in lung adenocarcinoma.",
        locator={"page": 12, "section": "Results"},
        authors=["Alice"],
        year=2024,
        doi="10.1234/demo",
        content_hash="sha256:x",
        domain="oncology",
    )


def test_normalize_doi_to_clickable_url():
    """DOI 规范化为 https://doi.org/..."""
    assert normalize_source_url(doi="10.1234/demo", url=None) == "https://doi.org/10.1234/demo"


def test_markdown_contains_jump_anchor_quote_and_status():
    """Markdown 含声明跳转、锚点、原文与支持状态。"""
    item = build_citation_item(
        claim_id="CLAIM-9",
        card=_card(),
        support_status=SupportDecision.ALLOW.value,
    )
    md = render_citation_markdown([item])
    assert "CLAIM-9" in md
    assert evidence_anchor_id("EV-CITE-1") in md
    assert "EGFR inhibition improves response" in md
    assert "p.12" in md
    assert "https://doi.org/10.1234/demo" in md
    assert "allow" in md
    jump = render_claim_to_evidence_jump("CLAIM-9", "EV-CITE-1")
    assert jump.startswith("[claim CLAIM-9")


def test_t08_payload_includes_upstream_and_fields():
    """T08 payload 含 upstream_ref 与可序列化 citations。"""
    item = build_citation_item(
        claim_id="CLAIM-9",
        card=_card(),
        support_status=SupportDecision.DEGRADE.value,
        support_note="cross-domain",
    )
    payload = build_t08_citation_payload(
        [item],
        upstream_ref="integration/2026-08-10 + t01/b-evidence-core",
    )
    data = payload.to_dict()
    assert data["schema_version"] == "t01-citation-payload-v1"
    assert "integration/2026-08-10" in data["upstream_ref"]
    assert data["citations"][0]["quoted_text"].startswith("EGFR")
    assert data["citations"][0]["locator"]["page"] == 12
    assert data["citations"][0]["support_status"] == "degrade"
    assert "Citations" in data["markdown"]


def test_gold_set_expanded_to_at_least_24_loadable_pairs():
    """黄金集扩展为 ≥24 条且可机器加载。"""
    pairs = load_evidence_gold_set()
    assert gold_set_count() >= 24
    assert len(pairs) >= 24
    assert pairs[0]["claim_id"] == "CLAIM-001"
    assert pairs[-1]["claim_id"] == "CLAIM-024"
    assert all(p.get("quote") for p in pairs)
    assert all(isinstance(p.get("locator"), dict) and p["locator"] for p in pairs)
