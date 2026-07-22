"""
tests/test_pipeline_mock.py — 工作流与客户端 mock 测试。

覆盖：
    - PIPELINE_STAGES 顺序完整；
    - PipelineState 可正常构造；
    - 骨架 run_pipeline 抛出 NotImplementedError；
    - MOCK_LLM 模式下 QwenChatClient 返回固定内容（无需真实 Key）；
    - MOCK_RERANK 模式下 RerankClient 返回可预测排序；
    - DeepResearch 未配置时返回 failed（不中断流程）；
    - EmbeddingClient 在 local_qwen 后端下抛出 NotImplementedError。
"""

from __future__ import annotations

import pytest

from app.core.constants import PIPELINE_STAGES
from app.core.schemas import PipelineState, QuestionItem
from app.workflow.pipeline import run_pipeline


def test_pipeline_stages_order():
    """阶段列表应包含 10 个阶段且首尾正确。"""
    assert len(PIPELINE_STAGES) == 10
    assert PIPELINE_STAGES[0] == "question_parser"
    assert PIPELINE_STAGES[-1] == "schema_validator"


def test_pipeline_state_construction():
    """PipelineState 应能构造并保留问题。"""
    q = QuestionItem(id="Q1", domain="D", question="Q?")
    state = PipelineState(run_id="r1", selected_question=q)
    assert state.selected_question.question == "Q?"


def test_run_pipeline_unknown_question_raises():
    """run_pipeline 对未知 question_id 应抛出 ValueError（已实现，不再是骨架）。"""
    # "示例问题" 不是合法 question_id，应清晰报错。
    with pytest.raises(ValueError):
        run_pipeline("示例问题", mock_mode=True)


def test_qwen_chat_mock(monkeypatch):
    """MOCK_LLM=true 时 chat 返回固定文本，chat_json 返回固定 JSON。"""
    # 启用 mock 模式，避免真实网络与 Key 依赖。
    monkeypatch.setenv("MOCK_LLM", "true")
    from app.clients.qwen_chat_client import QwenChatClient

    client = QwenChatClient()
    text = client.chat([{"role": "user", "content": "hi"}], model="qwen3.7-plus")
    assert "MOCK" in text
    data = client.chat_json([{"role": "user", "content": "hi"}], model="qwen3.7-plus")
    assert data.get("mock") is True


def test_qwen_chat_rejects_non_qwen(monkeypatch):
    """即便在 mock 模式，传入非千问模型也应被拒绝。"""
    monkeypatch.setenv("MOCK_LLM", "true")
    from app.clients.qwen_chat_client import QwenChatClient

    client = QwenChatClient()
    with pytest.raises(ValueError):
        client.chat([{"role": "user", "content": "hi"}], model="gpt-4o")


def test_rerank_mock(monkeypatch):
    """MOCK_RERANK=true 时 rerank 返回可预测的降序排序。"""
    monkeypatch.setenv("MOCK_RERANK", "true")
    from app.clients.rerank_client import RerankClient

    client = RerankClient()
    result = client.rerank("query", ["doc a", "doc b", "doc c"], top_k=2)
    # 应返回 top_k=2 条，且首条索引为 0。
    assert len(result) == 2
    assert result[0][0] == 0
    assert client.last_used_fallback is False


def test_deep_research_not_configured_returns_failed(monkeypatch):
    """未配置深度研究 endpoint 时应返回 failed，而非抛异常。"""
    from app.clients.qwen_deep_research_client import QwenDeepResearchClient

    class _StubSettings:
        deep_research_configured = False
        qwen_deep_research_model = "qwen-deep-research"
        dashscope_api_key = ""

    client = QwenDeepResearchClient(settings=_StubSettings())  # type: ignore[arg-type]
    result = client.run_deep_research("测试主题")
    assert result["status"] == "failed"
    assert result["content"] == ""


def test_embedding_local_backend_not_implemented(monkeypatch):
    """local_qwen 后端应抛出 NotImplementedError（可选增强，非默认）。"""
    from app.core.config import Settings
    from app.clients.embedding_client import EmbeddingClient

    # 构造 local_qwen 后端的配置注入客户端。
    settings = Settings(EMBEDDING_BACKEND="local_qwen")
    client = EmbeddingClient(settings=settings)
    with pytest.raises(NotImplementedError):
        client.embed_texts(["hello"])
