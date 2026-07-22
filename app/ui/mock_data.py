"""
app.ui.mock_data —— 前端 mock 展示数据兜底。

当尚无任何运行、又想让前端有内容可展示时，提供**明确标记 mock_for_testing**
的占位数据。严禁伪装成真实科研结论：Results 保持 pending，validation_status
不得为 validated，证据不含真实 DOI/URL。
"""

from __future__ import annotations

# 统一 mock 标记（前端据此渲染 amber 徽标）。
MOCK_TAG = "mock_for_testing"

# 前端 mock 说明文案。
MOCK_NOTICE = "Mock 模式：以下为界面演示数据（mock_for_testing），不代表真实科研结论；Results 为 pending。"


def mock_evidence_preview() -> list[dict]:
    """
    返回若干条 mock EvidenceCard（用于无运行时的证据墙预览）。

    返回：
        EvidenceCard 兼容 dict 列表（均含 mock_for_testing 标记，无真实 DOI/URL）。
    """
    return [
        {
            "id": "EV-MOCK-PREVIEW-1", "source_type": "rag", "title": "[MOCK] Local RAG excerpt",
            "authors": [], "year": None, "url": None, "doi": None,
            "quoted_text": "土地利用变化与外溢风险关联（mock 预览片段）。", "summary": "mock 背景证据。",
            "relevance_score": 0.8, "reliability_note": f"{MOCK_TAG}; source=local_rag",
        },
        {
            "id": "EV-MOCK-PREVIEW-2", "source_type": "deep_research", "title": "[MOCK] DeepResearch summary",
            "authors": [], "year": None, "url": None, "doi": None,
            "quoted_text": "One Health 与多源数据融合（mock 调研纪要）。", "summary": "mock 调研纪要。",
            "relevance_score": 0.6, "reliability_note": f"{MOCK_TAG}; requires downstream verification.",
        },
    ]


def is_mock_evidence(card: dict) -> bool:
    """判断一张证据是否为 mock（reliability_note 含 mock_for_testing）。"""
    return MOCK_TAG in (card.get("reliability_note") or "")
