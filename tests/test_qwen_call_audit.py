"""
tests/test_qwen_call_audit.py — Qwen 调用审计测试（P0-2）。

覆盖：
    - MOCK_LLM=true：qwen_call_count==0，mock_call_count>0；
    - real 模式（monkeypatch 注入 chat client）：qwen_call_count>0，记录 request_id；
    - real 模式调用失败：记录 status=failed，且抛错不静默 fallback 到 mock；
    - llm_call_audit 记录不含 API Key。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.agents.base import AgentOutputError
from app.core.call_audit import LLMCallRecord, summarize_calls
from app.core.schemas import PipelineState, QuestionItem

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"


def _state() -> PipelineState:
    """构造最小 PipelineState。"""
    q = QuestionItem(id="Q001", domain="Mathematical Sciences", question="What makes prime numbers so special?")
    return PipelineState(run_id="test-run", selected_question=q)


class _FakeChatClient:
    """伪造 chat client：返回固定 JSON 并暴露 request_id / usage。"""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.last_request_id = "req-abc123456"
        self.last_usage = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}

    def chat_json(self, messages, model, temperature=0.1):
        if self.fail:
            self.last_request_id = None
            raise RuntimeError("Connection error.")
        return {
            "domain": "Mathematical Sciences", "core_question": "prime",
            "keywords": ["prime"], "entities": ["e"], "question_type": "theoretical_proof",
            "scientific_boundary": "b", "what_not_to_claim": ["x"],
            "suspected_domain_mismatch": False, "domain_confidence": 0.9,
        }


def test_mock_mode_no_qwen_calls(monkeypatch):
    """mock 模式：无真实 Qwen 调用，mock 调用计数 > 0。"""
    monkeypatch.setenv("MOCK_LLM", "true")
    from app.agents.question_parser import QuestionParserAgent

    state = _state()
    agent = QuestionParserAgent()
    agent.run({"question_item": state.selected_question.model_dump()}, state, 0)
    summary = summarize_calls(state.llm_calls)
    assert summary["qwen_call_count"] == 0
    assert summary["mock_call_count"] >= 1


def test_real_mode_records_qwen_call(monkeypatch):
    """real 模式（注入 client）：记录真实 Qwen 调用与 request_id。"""
    monkeypatch.delenv("MOCK_LLM", raising=False)
    from app.agents.question_parser import QuestionParserAgent

    state = _state()
    agent = QuestionParserAgent(chat_client=_FakeChatClient())
    agent.run({"question_item": state.selected_question.model_dump()}, state, 0)
    summary = summarize_calls(state.llm_calls)
    assert summary["qwen_call_count"] >= 1
    assert summary["mock_call_count"] == 0
    assert summary["request_ids_masked"], "应记录脱敏 request_id"


def test_real_mode_failure_no_silent_fallback(monkeypatch):
    """real 模式调用失败：抛出 AgentOutputError，并记录 status=failed。"""
    monkeypatch.delenv("MOCK_LLM", raising=False)
    from app.agents.question_parser import QuestionParserAgent

    state = _state()
    agent = QuestionParserAgent(chat_client=_FakeChatClient(fail=True))
    with pytest.raises(AgentOutputError):
        agent.run({"question_item": state.selected_question.model_dump()}, state, 0)
    # 失败记录存在且不静默成功。
    failed = [c for c in state.llm_calls if c.get("status") == "failed"]
    assert failed, "失败调用必须记录 status=failed"
    assert all(not c.get("mock") for c in failed), "real 失败不得记为 mock"


def test_audit_record_has_no_api_key():
    """审计记录字段不含 API Key，key_masked 恒为 True。"""
    rec = LLMCallRecord(run_id="r", agent_name="a", provider="bailian_qwen").finalize()
    dumped = json.dumps(rec.model_dump(), ensure_ascii=False)
    assert "sk-" not in dumped
    assert rec.key_masked is True


def test_deep_research_real_audit_preserves_request_id_and_usage(monkeypatch):
    """DeepResearch 真实返回的 request_id 与完整 usage 必须写入调用审计。"""
    from app.agents.deep_research_agent import DeepResearchAgent

    class _FakeDeepResearchClient:
        """提供无网络的真实响应双桩及与生产客户端一致的最近元数据字段。"""

        last_request_id = "dr-request-123"
        last_usage = {"input_tokens": 11, "output_tokens": 13, "total_tokens": 24}

        def run_deep_research(self, topic, context=""):
            """返回已经由服务端确认的最小 DeepResearch 成功负载。"""
            return {
                "status": "succeeded",
                "content": "研究纪要",
                "references": [],
                "request_id": self.last_request_id,
                "usage": self.last_usage,
            }

    monkeypatch.delenv("MOCK_LLM", raising=False)
    monkeypatch.setattr(DeepResearchAgent, "is_mock", lambda _self: False)
    state = _state()
    agent = DeepResearchAgent(dr_client=_FakeDeepResearchClient())
    agent.run({"topic": "审计测试"}, state)
    record = state.llm_calls[-1]
    assert record["provider"] == "dashscope_deepresearch"
    assert record["request_id"] == "dr-request-123"
    assert (record["input_tokens"], record["output_tokens"], record["total_tokens"]) == (11, 13, 24)


def test_deep_research_usage_accepts_official_finished_pair():
    """官方 finished 分片只有 input/output 时，必须补齐 total 且不得丢弃用量。"""
    from app.clients.qwen_deep_research_client import QwenDeepResearchClient

    usage = QwenDeepResearchClient._normalized_usage(
        {"input_tokens": 21, "output_tokens": 7}
    )
    assert usage == {"input_tokens": 21, "output_tokens": 7, "total_tokens": 28}


def test_deep_research_usage_rejects_mismatched_total():
    """total 与 input+output 对不上时必须 fail-closed，不能改写服务端数字。"""
    from app.clients.qwen_deep_research_client import QwenDeepResearchClient

    assert QwenDeepResearchClient._normalized_usage(
        {"input_tokens": 3, "output_tokens": 4, "total_tokens": 9}
    ) == {}


def test_deep_research_request_id_from_output_and_headers():
    """request_id 可出现在 output 或响应头；提取逻辑不得编造标识。"""
    from app.clients.qwen_deep_research_client import QwenDeepResearchClient

    nested = QwenDeepResearchClient._extract_request_id(
        {"output": {"request_id": "dr-from-output"}}
    )
    headered = QwenDeepResearchClient._extract_request_id(
        {"headers": {"X-DashScope-Request-Id": "dr-from-header"}}
    )
    missing = QwenDeepResearchClient._extract_request_id({"output": {"message": {}}})
    assert nested == "dr-from-output"
    assert headered == "dr-from-header"
    assert missing == ""


def test_deep_research_stream_finished_chunk_preserves_audit(monkeypatch):
    """模拟官方 finished 分片：无 total_tokens 时仍写出 request_id 与完整 usage。"""
    import sys
    import types

    from app.clients.qwen_deep_research_client import QwenDeepResearchClient

    class _StubSettings:
        """最小可运行配置，避免读取宿主 .env 或发起真实网络。"""

        deep_research_configured = True
        qwen_deep_research_model = "qwen-deep-research"
        dashscope_api_key = "test-key"
        dashscope_deep_research_base_url = "https://example.invalid/api/v1"
        deep_research_timeout_seconds = 5

    class _FakeGeneration:
        """按官方文档顺序产出 answer 分片和 finished 用量分片。"""

        @staticmethod
        def call(**_kwargs):
            """返回无网络的两段流：正文 + finished usage。"""
            return iter(
                (
                    {
                        "request_id": "",
                        "output": {
                            "message": {
                                "phase": "answer",
                                "content": "调研纪要",
                                "extra": {"deep_research": {"references": []}},
                            }
                        },
                    },
                    {
                        "request_id": "dr-finished-456",
                        "output": {"message": {"phase": "answer", "status": "finished"}},
                        "usage": {"input_tokens": 15, "output_tokens": 9},
                    },
                )
            )

    fake_module = types.ModuleType("dashscope")
    fake_module.base_http_api_url = ""
    fake_module.Generation = _FakeGeneration
    monkeypatch.setitem(sys.modules, "dashscope", fake_module)

    client = QwenDeepResearchClient(settings=_StubSettings())  # type: ignore[arg-type]
    result = client.run_deep_research("审计测试")
    assert result["status"] == "succeeded"
    assert result["request_id"] == "dr-finished-456"
    assert result["usage"] == {"input_tokens": 15, "output_tokens": 9, "total_tokens": 24}
    assert client.last_request_id == "dr-finished-456"
    assert client.last_usage["total_tokens"] == 24


def test_full_mock_pipeline_audit_written(monkeypatch):
    """mock 全流程：审计文件写入且 qwen_call_count==0。"""
    if not QUESTIONS.exists():
        pytest.skip("缺少 questions_125.json")
    monkeypatch.setenv("MOCK_LLM", "true")
    from app.workflow.pipeline import run_pipeline_with_state

    _, state = run_pipeline_with_state("Q001", mock_mode=True)
    audit = Path(os.environ["SAGE_TEST_EXPORT_DIR"]) / state.run_id / "llm_call_audit.json"
    assert audit.exists(), "应写入 llm_call_audit.json"
    data = json.loads(audit.read_text(encoding="utf-8"))
    assert data["summary"]["qwen_call_count"] == 0
    assert data["summary"]["mock_call_count"] > 0
    assert "sk-" not in json.dumps(data, ensure_ascii=False)
