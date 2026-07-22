"""
tests/test_agent_trace.py — Agent 追踪测试。

覆盖：agent_trace.json 存在且包含关键 Agent；每条 trace 有
model_name/status/input_summary/output_summary/prompt_hash；不含完整 API Key。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.workflow.pipeline import run_pipeline_with_state

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"

pytestmark = pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")

# 必须出现的关键 Agent。
_REQUIRED = {
    "question_parser", "query_planner", "evidence_extractor", "hypothesis_generator",
    "experiment_designer", "scientific_reviewer", "report_writer", "schema_validator",
}


def _first_qid() -> str:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))[0]["id"]


def test_agent_trace(monkeypatch):
    """agent_trace 应覆盖关键 Agent 且字段完整、无 Key 泄露。"""
    monkeypatch.setenv("MOCK_LLM", "true")
    plan, state = run_pipeline_with_state(_first_qid(), mock_mode=True)

    trace_path = Path(os.environ["SAGE_TEST_EXPORT_DIR"]) / state.run_id / "agent_trace.json"
    assert trace_path.exists()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    names = {ev["agent_name"] for ev in trace}
    assert _REQUIRED.issubset(names)

    for ev in trace:
        # 关键字段齐备。
        assert ev.get("model_name")
        assert ev.get("status")
        assert "input_summary" in ev
        assert "output_summary" in ev
        assert ev.get("prompt_hash")
        # 不含完整 Key（沿用 sk- 长串检测）。
        blob = json.dumps(ev, ensure_ascii=False)
        assert "sk-" not in blob or "sk-****" in blob
