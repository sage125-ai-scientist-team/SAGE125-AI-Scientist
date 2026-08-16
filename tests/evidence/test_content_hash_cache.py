"""
T01 Wave C：内容哈希缓存与同输入证据集合确定性。
"""

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)
from app.core.schemas import EvidenceCard
from app.evidence.bundle_builder import ClaimSpec, build_evidence_bundle
from app.evidence.content_hash_cache import (
    ContentHashCache,
    assert_same_input_stable_evidence_set,
    deterministic_bundle_digest,
    get_global_content_hash_cache,
    stable_sort_evidence_ids,
)


def _runtime_card(evidence_id: str = "EV1") -> EvidenceCard:
    """
    构造运行时 EvidenceCard 夹具。

    参数：
        evidence_id: 证据 ID。

    返回：
        EvidenceCard。
    """
    return EvidenceCard(
        id=evidence_id,
        source_type="arxiv",  # type: ignore[arg-type]
        title="EGFR paper",
        authors=["A"],
        year=2024,
        doi="10.1234/egfr",
        quoted_text=(
            "EGFR inhibition improves response in lung adenocarcinoma samples."
        ),
        summary="summary",
        relevance_score=0.9,
        reliability_note="page=2; section=Results",
    )


def test_cache_hit_and_miss():
    """缓存未命中后写入，再次读取应命中。"""
    cache = ContentHashCache()
    digest1 = cache.get_or_compute("hello evidence quote text")
    assert cache.stats.misses >= 1
    digest2 = cache.get_or_compute("hello evidence quote text")
    assert digest1 == digest2
    assert cache.stats.hits >= 1


def test_get_or_compute_skips_hash_fn_on_hit():
    """红灯：命中时不得再次调用 hash_fn（真正避免重复哈希）。"""
    calls: list[str] = []

    def counting_hash(text: str) -> str:
        """
        记录调用次数的测试用哈希。

        参数：
            text: 原文。

        返回：
            伪哈希字符串。
        """
        calls.append(text)
        return f"sha256:count:{len(calls)}:{text}"

    cache = ContentHashCache()
    quote = "same quote must not re-hash"
    first = cache.get_or_compute(quote, hash_fn=counting_hash)
    second = cache.get_or_compute(quote, hash_fn=counting_hash)
    third = cache.get_or_compute(quote, hash_fn=counting_hash)
    assert first == second == third
    assert len(calls) == 1
    assert cache.stats.hash_fn_calls == 1
    assert cache.stats.hits == 2
    assert cache.stats.misses == 1


def test_stable_evidence_id_sort():
    """证据 ID 排序确定性。"""
    assert stable_sort_evidence_ids(["EV-B", "EV-A", "EV-B"]) == [
        "EV-A",
        "EV-B",
    ]


def test_same_input_bundle_digest_stable():
    """同输入两次构建 Bundle，指纹一致。"""
    cards = [_runtime_card()]
    claims = [
        ClaimSpec(
            claim_id="C1",
            evidence_ids=["EV1"],
            relation="supports",
            claim_domain="oncology",
        )
    ]
    left = build_evidence_bundle(
        cards,
        bundle_id="B-DET-1",
        claims=claims,
        token_budget=4000,
        domain="oncology",
    ).bundle
    right = build_evidence_bundle(
        cards,
        bundle_id="B-DET-1",
        claims=claims,
        token_budget=4000,
        domain="oncology",
    ).bundle
    assert_same_input_stable_evidence_set(left, right)
    assert deterministic_bundle_digest(left) == deterministic_bundle_digest(
        right
    )


def test_global_cache_singleton():
    """全局缓存单例可清空。"""
    cache = get_global_content_hash_cache()
    cache.clear()
    cache.get_or_compute("singleton-quote")
    assert cache.stats.size == 1
    cache.clear()
    assert cache.stats.size == 0


def test_contract_bundle_digest_roundtrip():
    """契约 Bundle 指纹在 model_dump 往返后仍稳定。"""
    card = EvidenceCardContract(
        evidence_id="EV-X",
        source_id="s",
        source_type="paper",
        title="T",
        quoted_text="Stable quote for digest roundtrip testing path.",
        locator={"page": 1},
        authors=["A"],
        year=2023,
        doi="10.1/x",
        content_hash="sha256:x",
        domain="medicine",
    )
    bundle = EvidenceBundle(
        bundle_id="B-X",
        evidences=[card],
        links=[
            ClaimEvidenceLink(
                claim_id="C",
                evidence_id="EV-X",
                relation="context",
            )
        ],
    )
    again = EvidenceBundle.model_validate(bundle.model_dump(mode="json"))
    assert deterministic_bundle_digest(bundle) == deterministic_bundle_digest(
        again
    )
